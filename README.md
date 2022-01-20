# validators-alerting-service
Simple function that detects decreasing ETH/Gnosis validator's balance and alerts the user.

## Requirements
* `Python 3+`
* `pip3`

## .env file content
```bash
NETWORK=mainnet # Network Name
DATABASE=validators.db # Local or remote DB name/url
BEACON_URL=http://localhost:3500 # Main beacon node
BEACON_FALLBACK_URL=http://localhost:5052 # Fallback beacon node
MISSED_ATTESTATIONS_ALLOWANCE=3 # Maximum amount of missed attestation before triggering an alert
TABLE_NAME=mainnet_validators # Name of the table in database
OPSGENIE_KEY=string # API Key for OpsGenie alerting service
OPSGENIE_TEAM_ID=string # Id of the routing team
SPREADSHEET=url # Just a reference to the dashboard/file with validators lookup
VALIDATORS=1111,1112 # String of comma separated validator indexes
```

## Installing packages
```bash
pip3 install -r requirements.txt
```

## Running the script
```bash
python3 main.py
```