from locust import HttpUser, task, between
from requests.auth import HTTPBasicAuth
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class OpenBMCTester(HttpUser):
    wait_time = between(1, 3)
    host = "https://127.0.0.1:2443"

    auth = HTTPBasicAuth("root", "0penBmc")

    @task(1)
    def get_system_info(self):
        response = self.client.get(
            "/redfish/v1/Systems/system",
            auth=self.auth,
            verify=False,
            name="OpenBMC: Get System Info"
        )
        if response.status_code in [200, 201, 202, 204]:
            try:
                data = response.json()
                if not ("Id" in data and "Name" in data):
                    print("Invalid system info structure")
            except json.JSONDecodeError:
                print("Invalid JSON for system info")
        else:
            print(f"Unexpected status code: {response.status_code}")

    @task(2)
    def get_power_state(self):
        response = self.client.get(
            "/redfish/v1/Systems/system",
            auth=self.auth,
            verify=False,
            name="OpenBMC: Get Power State"
        )

        if response.status_code in [200, 201, 202, 204]:
            try:
                data = response.json()
                state = data.get("PowerState")
                if state not in ["On", "Off", "PoweringOn", "PoweringOff"]:
                    print(f"Invalid PowerState: {state}")
            except json.JSONDecodeError:
                print("Invalid JSON for power state")
        else:
            print(f"Unexpected status code: {response.status_code}")
