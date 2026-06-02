import base64
import secrets
import time
import requests

from .mcs import ChromeBuildProto, AndroidCheckinProto, AndroidCheckinRequest, AndroidCheckinResponse

CHECKIN_URL = 'https://android.clients.google.com/checkin'


class AndroidFCM:

    @staticmethod
    def register(api_key, project_id, gcm_sender_id, gms_app_id, android_package_name, android_package_cert):
        # create firebase installation
        installation_auth_token = AndroidFCM.install_request(api_key, project_id, gms_app_id,                                                             
                                                             android_package_name, android_package_cert)
                
        # Checkin with GCM
        check_in_response = AndroidFCM.gcm_check_in()
        
        time.sleep(3) #等待三秒是因为如果check_in 之后立刻register容易报错，

        print(check_in_response)
        
        # Register with GCM
        fcm_token = AndroidFCM.register_request(
            check_in_response['androidId'],
            check_in_response['securityToken'],
            installation_auth_token,
            api_key,
            gcm_sender_id,
            gms_app_id,
            android_package_name,
            android_package_cert
        )

        return {
            'gcm': {
                'androidId': check_in_response['androidId'],
                'securityToken': check_in_response['securityToken'],
            },
            'fcm': {
                'token': fcm_token,
            }
        }

    @staticmethod
    def gcm_check_in(android_id=None, security_token=None):
        """
        Perform check-in request

        androidId, securityToken can be provided if we already did the initial check-in

        returns dict with androidId, securityToken, and more
        """
        chrome = ChromeBuildProto()
        chrome.platform = 2
        chrome.chrome_version = "98.0.3234.0"
        chrome.channel = 1

        checkin = AndroidCheckinProto()
        checkin.type = 3
        checkin.chrome_build = chrome

        payload = AndroidCheckinRequest()
        payload.user_serial_number = 0
        payload.checkin = checkin
        payload.version = 3
        if android_id:
            payload.id = int(android_id)
        if security_token:
            payload.security_token = int(security_token)

        retries = 5
        resp_data = None
        for _ in range(retries):
            try:
                response = requests.post(
                    url=CHECKIN_URL,
                    headers={"Content-Type": "application/x-protobuf"},
                    data=payload.SerializeToString()
                )
                response.raise_for_status()  # Raises an HTTPError if the response was unsuccessful
                resp_data = response.content
                break
            except requests.RequestException as e:
                time.sleep(1)
                continue

        if resp_data is None:
            return None

        resp = AndroidCheckinResponse()
        resp.parse(resp_data)
        return resp.to_dict()

    @staticmethod
    def install_request(api_key, project_id, gms_app_id, android_package, android_cert):
        # send firebase installation request
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Android-Package": android_package,
            "X-Android-Cert": android_cert,
            "x-firebase-client": "H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
            "x-firebase-client-log-type": "3",
            "x-goog-api-key": api_key,
            "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 9; Xiaomi-sagit Build/PKQ1.190118.001)"
        }
        body = {
            "fid": AndroidFCM.generate_firebase_fid(),
            "appId": gms_app_id,
            "authVersion": "FIS_v2",
            "sdkVersion": "a:17.2.0"
        }

        response = requests.post(
            f"https://firebaseinstallations.googleapis.com/v1/projects/{project_id}/installations",
            headers=headers,
            json=body
        )

        data = response.json()

        print(data)

        # Ensure auth token received
        if not data or 'authToken' not in data or 'token' not in data['authToken']:
            raise Exception(f"Failed to get Firebase installation AuthToken: {data}")

        return data['authToken']['token']

    @staticmethod
    def register_request(android_id, security_token, installation_auth_token, api_key, gcm_sender_id, gms_app_id,
                               android_package_name, android_package_cert, retry=0):
        headers = {
            "Authorization": f"AidLogin {android_id}:{security_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "device": android_id,
            "app": android_package_name,
            "cert": android_package_cert,
            "app_ver": "1",
            "X-subtype": gcm_sender_id,
            "X-app_ver": "1",
            "X-osv": "29",
            "X-cliv": "fiid-23.4.1",
            "X-gmsv": "220217001",
            "X-scope": "*",
            "X-Goog-Firebase-Installations-Auth": installation_auth_token,
            "X-gms_app_id": gms_app_id,
            "x-firebase-client": "H4sIAAAAAAAAAKtWykhNLCpJSk0sKVayio7VUSpLLSrOzM9TslIyUqoFAFyivEQfAAAA",
            "X-Firebase-Client-Log-Type": "1",
            "X-app_ver_name": "1",
            "target_ver": "31",
            "sender": gcm_sender_id
        }

        response = requests.post(
            "https://android.clients.google.com/c2dm/register3",
            headers=headers,
            data=data
        )

        response_text = response.text
        
        # Retry a few times if needed
        if 'Error' in response_text:
            print(f"Register request has failed with {response_text}")
            if retry >= 5:
                raise Exception('GCM register has failed')
            print(f"Retry... {retry + 1}")
            time.sleep(2)
            return AndroidFCM.register_request(android_id, security_token, installation_auth_token, api_key,
                                               gcm_sender_id, gms_app_id, android_package_name,
                                               android_package_cert, retry + 1)

        # extract fcm token from response

        print(response_text)
        return response_text.split('=')[1]

    @staticmethod
    def generate_firebase_fid():
        # A valid FID has exactly 22 base64 characters, which is 132 bits, or 16.5
        # bytes. Our implementation generates a 17 byte array instead.
        fid = bytearray(secrets.token_bytes(17))

        # Replace the first 4 random bits with the constant FID header of 0b0111.
        fid[0] = 0b01110000 + (fid[0] % 0b00010000)

        return base64.b64encode(fid).decode('utf-8')
