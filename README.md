# iot-bms-link

A cloud-BMS gateway driver for IoT applications.

## Setup

### 1. Install Python and Poetry

#### On Arch Linux:

```bash
sudo pacman -S python
sudo pacman -S python-poetry
```

#### On Windows:

Download and install [python](https://www.python.org/downloads/)

```powershell
(Invoke-WebRequest -Uri https://install.python-poetry.org -UseBasicParsing).Content | python -
```

### 2. Clone the repository

```bash
git clone https://github.com/ehernaiz0602/iot-bms-link.git
cd iot-bms-link
```

### 3. Install project dependencies

```bash
poetry install
poetry shell
```

### 4. (OPTIONAL) Compile the project into an executable file:

#### On Windows:

```powershell
build.bat
```

## Usage

### Configuration requirements

On the first run, you may simply start the program once and let it stop. This will generate the default configuration files in the root directory, which you can then edit to suit your needs.
Before running, you must make sure that your configuration files are completely filled out.

### Running from source

You can run the program from source:

```bash
poetry shell
py src/main.py
```

If you have compiled the project into a single file on Windows by using the provided build.bat file, you can just run the executable.

## Configuration

The driver uses three JSON configuration files to control its behavior:

- **Settings-Azure.json** → Azure IoT Hub and Key Vault integration
- **Settings-General.json** → General runtime and logging options
- **Settings-IP.json** → Device IP addresses and panel definitions

---

### Settings-Azure.json

This file defines how the gateway authenticates and connects to Azure services.

**Fields:**

- `tenant_id` : Azure Active Directory tenant ID.
- `client_id` : Application (client) ID registered in Azure AD.
- `store_id` : Identifier for the certificate/key store.
- `scope_id` : DPS (Device Provisioning Service) scope ID.
- `secret_name` : Name of the secret in Key Vault used for authentication.
- `certificate_subject` : Subject name of the certificate used for secure connection.
- `vault_name` : Azure Key Vault name where secrets/certs are stored.
- `sas_ttl` : Time-to-live (in days) for generated SAS tokens (default: 90).

---

### Settings-General.json

This file controls logging, retry policies, publishing intervals, and failover behavior.

**Fields:**

- `logging_level` : Log verbosity, console only (`debug`, `info`, `warning`, `error`, `critical`).
- `log_file_max_size_mb` : Maximum log file size before rotation, in megabytes.
- `log_file_backup_count` : Number of rotated log files to keep.
- `http_request_delay` : Delay (seconds) between HTTP requests.
- `http_timeout_delay` : Timeout (seconds) for HTTP requests.
- `http_retry_count` : Number of retries for failed HTTP requests.
- `publish_interval_seconds` : The minimum cooldown (seconds) for publishing regular data.
- `publish_all_interval_hours` : Interval (hours) for publishing full dataset.
- `soft_reset_interval_hours` : Interval (hours) for performing a soft reset.
- `use_err_files` : Whether to show errors in the local directory as files, for running as a service.
- `write_iot_payload_to_local_file` : Whether to (over)write the last IoT payload to a local file.
- `fail_connection_number` : Number of consecutive BMS failures before triggering hard stop.
- `allowable_azure_downtime_minutes` : Grace period (minutes) allowed for Azure downtime before hard stop.
- `send_message_to_local_file_only` : If `true`, bypass IoT Hub and log messages locally (JSONL format) -- you still need a valid IoT connection and configuration.

---

### Settings-IP.json

This file defines the IP addresses of panels/controllers for different supported device types.

**Fields:**

- Top-level keys (`danfoss`, `emerson_e2`, `emerson_e3`) represent supported controller types.
- Each entry contains:
  - `ip` : IP address of the panel/controller.
  - `name` : Human-readable identifier for the panel.

Example:

```json
{
  "danfoss": [
    { "ip": "192.168.1.10", "name": "panel_01" },
    { "ip": "192.168.1.11", "name": "panel_02" }
  ],
  "emerson_e2": [{ "ip": "192.168.2.10", "name": "panel_01" }]
}
```

## Reporting Issues

If you encounter bugs, unexpected behavior, or have feature requests, please help improve the project by reporting them.

### How to report

1. Check the [issue tracker](https://github.com/ehernaiz0602/iot-bms-link/issues) to see if your problem has already been reported.
2. If not, open a new issue and include:
   - **Environment details**: operating system, Python version, Poetry version.
   - **Steps to reproduce**: a clear description of what you did.
   - **Expected behavior**: what you thought would happen.
   - **Actual behavior**: what actually happened, including error messages or logs.
   - **Configuration files** (if relevant): share the portion(s) of your configuration file(s) that relates to the problem.

### Feature requests

If you have ideas for improvements or new features:

- Describe the use case and why it would be helpful.
- Suggest possible implementation details if you have them.

### Security issues

For security-related concerns, please **do not** open a public issue.  
Instead, contact the maintainer directly via email listed in the repository profile.
