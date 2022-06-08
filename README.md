# BoozeCruise
Bot for managing our Booze Cruise activities for the Pilots Trade Network.  This bot offers multiple functionalities 
which are gated by discord roles.  The bot runs on a GCP instance.

All commands are in hierarchical format, so the higher roles can run everything below it.

### Admin Specific commands:

- ping: Send `b/ping` in order to validate the bot is online.
- version: Send `b/version` in order to print the bot version.
- update: Send `b/update` to restart the bot with the latest code on the server.
- exit: Send `b/exit` to close the bot completely.

### Sommelier (and admin):

- `wine_mark_completed_forcefully` - Marks a carrier as completed. This is a backup in case someone offloads on the 
  side, usually this would be marked with a general unload operation.
- `wine_carrier_unload <XXX-XXX: str> <planet: str> <market_type: str> <unload_channel: str [optional]>` - Sets an  
  unload notification for the carrier. Notification will be posted into a discord channel if TimedMarket and unload 
  channel provided.
- `wine_unloading_complete <XXX-XXX: str>` - Marks the carrier unload as completed and deletes the carrier notification.
  

### Carrier Owners and Aux Carrier Owners:

- `Wine_Helper_Market_Open` - Drops an embed into the channel to coordinate unloading.
- `Wine_Helper_Market_Closed` - Drops an embed into the channel to mark the market as closed.

### General Users

- `/find_carriers_with_wine` - Returns an embed with all the remaining wine
- `/find_carriers_by_id XXX-XXX` - Searches for the carrier XXX-XXX in the database and returns an object 
  representing it.
- `find_wine_carriers_for_platform <platform> <with-wine: bool>` - Returns all the carriers for the platform with 
  wine, or all carriers for the platform in total.

# Tech Notes

Run all tests with
```bash
python -m unittest discover
```
