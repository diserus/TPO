import time
import pytest
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

ADMIN_LOGIN = "root"
ADMIN_PASS = "0penBmc"
BLOCKED_LOGIN = "testuser"
BLOCKED_PASS = "test23pwd"
BASE_URL = "https://127.0.0.1:2443"


def setup_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-ssl-errors")
    service = Service("/geckodriver")

    driver = webdriver.Firefox(service=service, options=options)
    driver.implicitly_wait(10)
    return driver

def login(driver,user,password):
    driver.get(BASE_URL+"/login")
    username_field = driver.find_element(By.ID, 'username')  
    password_field = driver.find_element(By.ID, 'password')
    login_button = driver.find_element(By.XPATH, '//button[@type="submit"]')
    username_field.send_keys(user)
    password_field.send_keys(password)
    login_button.click()
    time.sleep(3)
def is_logged_in(driver):
    try:
        WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.ID, "app-header-user__BV_toggle_"))
        )
        return True
    except TimeoutException:
        return False
def test_login():
    try:
        driver = setup_driver()
        login(driver, ADMIN_LOGIN, ADMIN_PASS)
        assert is_logged_in(driver), "Не удалось войти в систему"
    finally:
        driver.quit()

def test_invalid_login():
    try:
        driver = setup_driver()
        login(driver, ADMIN_LOGIN, BLOCKED_PASS)
        assert not is_logged_in(driver), "Удалось войти с неверным паролем"
    finally:
        driver.quit()
def test_account_block_after_failed_attempts():
    try:
        driver = setup_driver()
        for i in range(5):
            login(driver, BLOCKED_LOGIN, ADMIN_PASS)            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            time.sleep(1)

        login(driver, BLOCKED_LOGIN, BLOCKED_PASS)            

        assert not is_logged_in(driver), "Удалось войти, хотя аккаунт должен быть заблокирован"
    finally:    
        driver.quit()
def test_power():
    try:
        driver = setup_driver()
        login(driver,ADMIN_LOGIN,ADMIN_PASS)
        time.sleep(3)
        driver.get(BASE_URL+"/?next=/login#/operations/server-power-operations")
        power_button = driver.find_element(By.XPATH, '//button[contains(text(), "Power on")]')
        power_button.click()
        time.sleep(3)
        powerstate_text = driver.find_element(By.CSS_SELECTOR,'[data-test-id="powerServerOps-text-hostStatus"]').text
        assert 'On' in powerstate_text, "Сервер не включился"
    finally:
        driver.quit()
def test_logs():
    try:
        driver = setup_driver()
        login(driver,ADMIN_LOGIN,ADMIN_PASS)
        time.sleep(3)
        driver.get(BASE_URL+"/?next=/login#/operations/server-power-operations")
        power_button = driver.find_element(By.XPATH, '//button[contains(text(), "Power on")]')
        power_button.click()
        time.sleep(3)
        driver.get(BASE_URL+"/?next=/login#/logs/event-logs")
        time.sleep(3)
        power_logs = driver.find_elements(By.XPATH, '//*[contains(text(), "Power on") or contains(text(), "error") or contains(text(), "Error")]')
        if power_logs:
                print("В логах найдена запись о включении питания")
                for log in power_logs:
                    print(f"{log.text}")
                assert True
        else:
            print("В логах нет записи о включении питания")
            assert False

    except Exception as e:
        print(f"Ошибка: {e}")
        raise
    finally:
        driver.quit()