# AMI Service Integration Note

## Important: AMI Service API

The dialer service needs to initiate outbound calls via the AMI (Asterisk Manager Interface) service. The current implementation in `avr-dialer/main.py` assumes the AMI service provides an HTTP endpoint:

```
POST /api/originate
```

## If Your AMI Service Doesn't Have This Endpoint

You have two options:

### Option 1: Update the Dialer Service

Modify the `initiate_call_via_ami()` function in `services/avr-dialer/main.py` to use your AMI service's actual API.

For example, if your AMI service uses a different endpoint:

```python
async def initiate_call_via_ami(...):
    # Replace this:
    response = await client.post(
        f"{ami_url}/api/originate",
        json={...}
    )
    
    # With your AMI service's actual endpoint:
    response = await client.post(
        f"{ami_url}/your/actual/endpoint",
        json={...}
    )
```

### Option 2: Use Asterisk AMI Directly

If you prefer to connect directly to Asterisk AMI (port 5038), you can use the `pyst2` library:

```python
from asterisk.ami import AMIClient

async def initiate_call_via_ami(...):
    client = AMIClient(address='avr-asterisk', port=5038)
    future = client.login(username='avr', secret='avr')
    
    if future.response.is_error():
        return {"status": "error", "message": "AMI login failed"}
    
    action = SimpleAction(
        'Originate',
        Channel=f"PJSIP/{phone_number}@trunk",
        Context=context,
        Exten=phone_number,
        Priority=1,
        CallerID=f"{caller_name} <{caller_id}>",
        Variable=f"CampaignID={campaign_id},NumberID={number_id}"
    )
    
    response = client.send_action(action)
    return {"status": "success", "call_uuid": response.response.get('Uniqueid')}
```

Don't forget to add `pyst2` to `requirements.txt`:

```
pyst2==0.5.0
```

### Option 3: Use ARI (Asterisk REST Interface)

If your Asterisk has ARI enabled, you can use the ARI API:

```python
async def initiate_call_via_ari(...):
    async with httpx.AsyncClient(auth=('avr', 'avr')) as client:
        # Create channel
        response = await client.post(
            f"http://avr-asterisk:8088/ari/channels",
            json={
                "endpoint": f"PJSIP/{phone_number}@trunk",
                "app": "dialer",
                "callerId": caller_id
            }
        )
        
        if response.status_code == 200:
            channel_id = response.json()['id']
            
            # Originate call
            await client.post(
                f"http://avr-asterisk:8088/ari/channels/{channel_id}/dial",
                json={"endpoint": f"PJSIP/{phone_number}@trunk"}
            )
            
            return {"status": "success", "channel_id": channel_id}
```

## Testing AMI Connection

To test if your AMI service is accessible:

```bash
# Test HTTP endpoint
curl http://localhost:6006/health

# Test AMI directly (if using telnet)
telnet localhost 5038
# Then login: Action: Login\nUsername: avr\nSecret: avr\n\n
```

## Current Implementation

The current dialer implementation uses HTTP to communicate with the AMI service. If your `avr-ami` service doesn't expose an `/api/originate` endpoint, you'll need to either:

1. Add that endpoint to your AMI service, or
2. Modify the dialer to use the AMI service's actual API, or
3. Connect directly to Asterisk AMI/ARI

Check your `avr-ami` service documentation or source code to see what endpoints it provides.

