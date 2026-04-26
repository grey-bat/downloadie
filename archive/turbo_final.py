import os
import json
import subprocess
import time

# Config
SSD_CACHE = "/Users/greg/takeout_cache"
HDD_BASE = "/Volumes/Backup/photos"
STATUS_FILE = "/Users/greg/Code/turbo/status_turbo.json"

# Auth details
JOB_ID = "86111f0a-cd80-45e8-82f2-61e5f8b37264"
USER_ID = "101514084415461963913"
BATCH_NAME = "batchTwo"
RAPT = "AEjHL4NQ2Re2VKmeh16okEh6fMK0E34qgabIYK_zVTrZA6oqb_q_JtjtU2bdNXcxVy02D-la1iVTQtpob_A9l0_YR3GoSBUqfExX15eAWf6Debm5YOsIrjM"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
REFERER = f"https://takeout.google.com/manage/archive/{JOB_ID}?download=true&rapt={RAPT}&quotaExceeded=true"
COOKIES = "__Secure-ENID=29.SE=rmlnN7YSDed4y4j9rpVdQr87lYGDWFgiTgOos0szYUKAFIa-8gfSrUeAoWjgd5G15qyw4UDA6ktwPWv250vwYukIT7rV09FqI7WDdE1s6d0xCbSB8LXyanbhD-nJ7RccY4NhppxFHxSYamRjH-EQ_48_FjJxtAxYo79o6kt6qK3gx3pi16_lVsyxjZYTdjPNLTOiZr18MfaALMlrPw6Ahfy4nS8m1l64aXyNkQj29Wx5d4ff_J9ahw7FKriRMvEe0DJnNxEpyGvW1PSTa2qhGKRwFoBHiRNP5hxj2XWW_SzgUaRxFYYKahE_8hkhCvrjqxKkZuxo6-xw0P3arMutCH3znv1JB6d3-n12Mbnk8QLVWW-GJzsTV4HyQaC6l7pah9uimg5f3cHoimUZfqYV36RZo7jk8nykBw; S=billing-ui-v3=WtmkSgCqPHyLBfAe1aTDXQLnmYn5LkNPWya3PQvuSzY:billing-ui-v3-efe=WtmkSgCqPHyLBfAe1aTDXQLnmYn5LkNPWya3PQvuSzY; __Secure-BUCKET=CKAB; SEARCH_SAMESITE=CgQI1p8B; OTZ=8409484_68_64_73560_68_416340; AEC=AaJma5vaE929TYhGUVA560sLMQ62DVcjhGcX3iFuuOLencyRNYZJ8yWLFw; NID=527=J-XL1aBoXP9iWnaa7yg0liz7deN0zQfVX9JepmV9Hy-vYtCIJaS9cAO6TYfUwSBODBMplbH3UsSu1WwsQNUztfWkqA5YHj5vKkYrEnf5yqm_9P0Ii93fuScHcfYHmk86WHaOHi93qxow7qtoaS9K5gkRFDEzdl1_t-TE2vHFGwh_8qjJOOyIYuR8pEWuT8hFUfuC1YM-I3s2Dtbuc9bS4qkFz38n4nga56NQbKmIY98idKEuOM2QcG2wD3kCmNH_WnPO2V_JcP6MAq7RHh7KAT_X33is3qdEozedhLbtRcV9I-zZ4zJGAiYnTHXEd8DQnNfvoCJeC92srco7Bgx3eickR8xIue_vRU5Oit1a_EgZi6_TwoZXD2JaA759vYaebl44LrQTwuzM4uYjO41fCwjgggU_FDLUx-UID2TlyI6FyMTK0OXF41MSPx3WEoi5tZhGMwUubxaVR9HalDq6A4nErVOEhhhUO1loN5BPWm9o4ahNaJoYcJyj_EzCzWUQCFDp_uxRUHVl0JVzrgRwzbXU7qTExapy0TywZ_NBspQ4dXJoeB-9jfT3y9ZvObkuhKqn-Xc1W0EIRMsU-wljtT-TXCzsgihpCdSY9rnJJDWyREaSM7vmdeXSCUkuDun6NlHDrhIEpMaxVkYBhZNI4hRSpZkEgzfU1EVGPXeX1jJ3oeUbBXI6zVMLKteeeurAR2s0P9JoV-zNZRIunbLprMkF6E1tbQbpK352SRF8SJqHyvRyA38GftD67BCWPVXg-gRttb6ZvSZg9nVgS3NX9M4dHiXoWTB_7h9CNooRZb8RuiRdjvpE-bs7E2T4yRXUAYZBZAWjOFxbiq-3Ejl5adpDFX7Y9dDlGqrr-dska_ei64Af1usmW_lNiNywDb1vw-0X-MZeuvxE73UemtzKU-M3e42uxEQ1ANIilFB0hwGCGWE8fGmbxdQndA043zAcvV-Ux7tRwE0YG0O8e0VdIXNzprkZ-CIpV_tA2q2BGRfqylm-pVVDkaBfO6mmCakrUe6_LPtRYI_2L0cJq8S9jTvw03KBT1RhqXLwBVwfV-nz1tM9VROttsnA3XhOpRAbjZ8U_o9Q_H6X5Re_a0dV1koM3in-C50gF87xJdV2d9TV-QU1x3tKrocQeIi3frrO_LcjhmUPE6WhbkeLrhLTqaqDD34aYXFdB3qdZRCfk9d4TJTORmNWZx3JoqyDsCKAf0JvhFOGmYbYSc7BaRe96YtXvTlXpjBEIFENwPUQv6KEvbubufyereQ9fFXekh6TbCGUxLnGS0y1x9ueHbZTSvHCmPW7CGTSqvIR6jYEpeUvuscInzriIYgiZjm9X4iemPB0LNu1dzy1dHXXa5ZVudZMzRBAuZCPTav4z7oUQAFHE2IE1ZDhApuWbQHAzz1aUltrUQzN9NKP1AW4Zuo2O1PS5pCYw2j_531qkC8IzIMec1iqe_FIall2-B5npR2CurtIC3DAxeOUt5Mm3TY2eb0UJbIZ2yWmQDg_ljfgu9uLUt1XcAKE4p8Niyh0qZ9IQy4c5z3YpuIWD3rxK3WqWuG4woPblo7r0DeODgwUCZ_QtDY8ixwGf8pqor5meoKH-IVQIUEfypig2cilRtnu78D45cU-ENfKzPoLKQri_WQa5OyO9zhn6_cxthGaJxgMBAdP3WGBIwe-dvIRmGJJvFzH61m506uC-aAc94cBJv17Z68X_fWdgcqw4uxOqLm5yLqqKiAq8-xGgxTWoHp-PnxxGxeL0WJ5c5cyEzz3gsb9zFlz4RuaaJZu601GDl8Yvommhlauqcbvfp45GvedjD2ZzhspYdyT8IkyIy977nLG1L147YLK3XOnUMqgWZ3nlddY6j_xTJC7gaDT8APSNcp0eNIcKtRHgJcHBNZHZfExOe1beQmbPkTEyDconqzT4EEZnmA1ZxZ4Gc0WQKZ6prmkySMBYduiSa5slcfjoF5b-741b4sK-hGerg5fU0GyFlSbLVokQXS_JWGYaQsI8qxRxOEOV7HliX58ntl7j4m2OSLI-_bDLw; __Secure-1PSIDTS=sidts-CjIBflaCde7ahmJoFxzHAibpgXEMuOBAerweBdL0IDgChqe6mNlkYitLTmpyCIu6VaKFJRAA; __Secure-3PSIDTS=sidts-CjIBflaCde7ahmJoFxzHAibpgXEMuOBAerweBdL0IDgChqe6mNlkYitLTmpyCIu6VaKFJRAA; SID=g.a0005QiqAk2uUrHfJAG9bqZ5s13BP9eJSfyQw8kXzhyNvN1jBt8cqpH-VZ7R67mIyyx1gplmgQACgYKAZQSARUSFQHGX2Mi2LLFa3Ipe8Kp5-iR_sF8RRoVAUF8yKrTlwZr3CBophqn1wMTvm540076; __Secure-1PSID=g.a0005QiqAk2uUrHfJAG9bqZ5s13BP9eJSfyQw8kXzhyNvN1jBt8c6-unVofUfP88QQIx4LINfQACgYKAc0SARUSFQHGX2MiQfYK6mhBOPl24tKxKdXetRoVAUF8yKocMum3cus2Mb99OuXQQgbk0076; __Secure-3PSID=g.a0005QiqAk2uUrHfJAG9bqZ5s13BP9eJSfyQw8kXzhyNvN1jBt8cyhkhUz6jW0ViWPNtFNpVQwACgYKATMSARUSFQHGX2MiZJPq8vJ8XlDgsknxeCe4gRoVAUF8yKrvM8HXqRzGNMbLixmY4sdp0076; HSID=A_5mh-c7sfQrALnKx; SSID=AXKXCE_ocoag5aZez; APISID=DkIhoierg96CnnlM/AMp6FPI4hwLkfie-W; SAPISID=EZiTW5oVC4dZVHRM/ABOi3Ki4e1rDcaBtA; __Secure-1PAPISID=EZiTW5oVC4dZVHRM/ABOi3Ki4e1rDcaBtA; __Secure-3PAPISID=EZiTW5oVC4dZVHRM/ABOi3Ki4e1rDcaBtA; OSID=g.a0005QiqAgitunWJOfHzUB_Pd6iqI1Y3fwyVYpsz1pSnxq9oXIJ8ePiSSnMRA5NZPZiXLE2bfAACgYKAbMSARUSFQHGX2MiIHDBb0OXqWybtZslvvL4UBoVAUF8yKoNMz87L4kAJCX7GLHgUUKS0076; __Secure-OSID=g.a0005QiqAgitunWJOfHzUB_Pd6iqI1Y3fwyVYpsz1pSnxq9oXIJ86Qx03QxR_raVIJ7vo7ANkwACgYKAaQSARUSFQHGX2MiTdHIvOaE2k9IOUmXdGO_4BoVAUF8yKpGBc1F6NbNOTWQQm0sd3J20076; SIDCC=AKEyXzXzs4SQEWMhaIVBPnOvHZZG4oKmLQbBToCjdwwhkF_gicym1fx-gLxzi541QpR-5IFwM_EX; __Secure-1PSIDCC=AKEyXzUiiIVfBPWn-tMy2ROp-tprbMvInZPiMoOpnrMIk0mXGGAhCesweo4zNQbR6YH6X03P0tkj; __Secure-3PSIDCC=AKEyXzU9TsBqpevhgJp1HBMUIjYusaz0OuelAarlMS8eQvWyp58YCGwGC4Gk-JCYxFZDJ9uikpY"

def update_board(status):
    try:
        with open(STATUS_FILE + ".tmp", "w") as f:
            json.dump(status, f)
        os.rename(STATUS_FILE + ".tmp", STATUS_FILE)
    except: pass

def run():
    status = {"batch": BATCH_NAME, "part": 0, "total_parts": 3, "phase": "IDLE", "speed": "0 MB/s", "progress": "0%", "file": ""}
    update_board(status)
    
    for i in range(3):
        file_name = f"takeout_{BATCH_NAME}_part{i+1}.zip"
        url = f"https://takeout.google.com/takeout/download?j={JOB_ID}&i={i}&user={USER_ID}&rapt={RAPT}"
        dest_path = os.path.join(SSD_CACHE, file_name)
        
        status.update({"part": i+1, "file": file_name, "phase": "DOWNLOADING", "progress": "0%", "speed": "0 MB/s"})
        update_board(status)
        
        cmd = [
            "aria2c", url, "--header", f"Cookie: {COOKIES}",
            "--header", f"User-Agent: {UA}",
            "--header", f"Referer: {REFERER}",
            "-d", SSD_CACHE, "-o", file_name,
            "-s", "16", "-x", "16", "-k", "1M",
            "--file-allocation=falloc", "--allow-overwrite=true", "--summary-interval=1"
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
            if "(" in line and "%)" in line and "DL:" in line:
                try:
                    parts = line.split()
                    for p in parts:
                        if "(" in p and "%)" in p: status["progress"] = p.strip("[]()")
                        if "DL:" in p: status["speed"] = p.replace("DL:", "")
                    update_board(status)
                except: pass
        proc.wait()
        
        if proc.returncode != 0 or not os.path.exists(dest_path) or os.path.getsize(dest_path) < 10 * 1024 * 1024:
            status["phase"] = "ERROR: Download failed or auth expired"
            update_board(status)
            return

        status.update({"phase": "EXTRACTING", "progress": "0%", "speed": "--"})
        update_board(status)
        
        out_dir = os.path.join(HDD_BASE, BATCH_NAME)
        os.makedirs(out_dir, exist_ok=True)
        
        ex_proc = subprocess.Popen(["/opt/homebrew/bin/7z", "x", dest_path, f"-o{out_dir}", "-y"], 
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in ex_proc.stdout:
            if "%" in line:
                try:
                    p = [x for x in line.split() if "%" in x][-1]
                    status["progress"] = p
                    update_board(status)
                except: pass
        ex_proc.wait()
        
        if ex_proc.returncode == 0:
            os.remove(dest_path)
            status["phase"] = "CLEANED"
            update_board(status)
        else:
            status["phase"] = "ERROR: Extraction failed"
            update_board(status)
            return

    status.update({"phase": "COMPLETE", "progress": "100%"})
    update_board(status)

if __name__ == "__main__":
    run()
