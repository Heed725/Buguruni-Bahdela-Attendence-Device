# Hikvision ISAPI Biometric Enrollment

A Streamlit interface for registering employees, face photographs, and fingerprints on a Hikvision access-control terminal through ISAPI. It was prepared for the **DS-K1T321MFWX** and uses HTTP Digest Authentication.

## Features

- Test the Hikvision connection and read device information.
- Create and update employees.
- Upload a JPEG face photograph.
- Capture a fingerprint on the terminal and apply it to an employee.
- Search registered employees.
- Keep credentials out of source control with Streamlit secrets.

## Security warning

Biometric information is sensitive personal data. Do not expose the device directly to the public internet. Prefer a VPN, restrict inbound traffic by firewall, use HTTPS where supported, change default passwords, and obtain appropriate authorization before enrolling people.

## Installation on Windows

```cmd
git clone YOUR_REPOSITORY_URL
cd hikvision-isapi-streamlit
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Create the local secrets file:

```cmd
copy .streamlit\secrets.toml.example .streamlit\secrets.toml
notepad .streamlit\secrets.toml
```

Replace `CHANGE_ME` with the current device administrator password. Never commit `secrets.toml`.

Start the application:

```cmd
streamlit run app.py
```

Open the address printed by Streamlit, normally `http://localhost:8501`.

## Server deployment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
nano .streamlit/secrets.toml
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

For a permanent deployment, run Streamlit behind Nginx and a systemd service. Store secrets on the server only.

## Face upload compatibility

Hikvision firmware versions can use different multipart image-field names. Start with `FaceImage`. If the device returns `Invalid Content`, retry from the interface using `img`, then `faceUrl`. The metadata field remains `FaceDataRecord`.

## Fingerprint enrollment

1. Create the employee first.
2. Enter the same employee number under **Fingerprint**.
3. Ask the employee to stand at the physical terminal.
4. Click **Capture and apply fingerprint**.
5. The employee places their finger on the sensor when prompted by the terminal.

The application does not store the returned fingerprint template. It immediately sends the template back to the terminal for enrollment.

## Configuration

| Secret | Description |
|---|---|
| `HIKVISION_URL` | Device URL including the HTTP port |
| `HIKVISION_USERNAME` | ISAPI administrator username |
| `HIKVISION_PASSWORD` | ISAPI password; never commit this value |
| `HIKVISION_TIMEOUT` | Request timeout in seconds |
| `HIKVISION_VERIFY_TLS` | Set to `true` only when HTTPS certificate validation is configured |

## Troubleshooting

- **401 Unauthorized:** verify username/password and Digest Authentication access.
- **Invalid Content:** verify the selected image multipart field or inspect the model-specific ISAPI guide.
- **Fingerprint data not returned:** ensure the employee touches the terminal sensor during capture.
- **Connection timeout:** check the public/private address, port, firewall, and VPN routing.
- **Employee not found:** create the employee before adding face or fingerprint information.

## Supported device capabilities verified

The target terminal reported support for `UserInfo`, `FDLib`, `CaptureFace`, `FingerPrintCfg`, `CaptureFingerPrint`, and `FingerPrintDelete`.
