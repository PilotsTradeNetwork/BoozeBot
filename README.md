# BoozeCruise

Bot for managing our Booze Cruise activities for the Pilots Trade Network. This bot offers multiple functionalities
which are gated by discord roles.

All commands are in hierarchical format, so the higher roles can run everything below it.

### Admin Specific commands:

-   ping: Send `b/ping` in order to validate the bot is online.
-   version: Send `b/version` in order to print the bot version.
-   sync: Send `b/sync, in order to sync the bot command tree to discord.
-   update: Send `b/update` to restart the bot with the latest code on the server.
-   exit: Send `b/exit` to close the bot completely.

### Sommelier:

-   `/wine_mark_completed_forcefully` - Marks a carrier as completed. This is a backup in case someone offloads on the side, usually this would be marked with a general unload operation.
-   `/booze_channels_open` - Opens all the public booze cruise channels.
-   `/booze_channels_close` - Closes all the public booze cruise channels.
-   `/clear_booze_roles` - Removes the 2 temporary booze cruise related roles (Hitchhiker & Wine Carrier) from all users.
-   `/set_wine_carrier_welcome` - Sets the message that is sent in #wine-carrier-chat when someone is granted wine carrier.
-   `/steve_says` - Sends a message as the bot.
-   `/remove_wine_carrier` - Removes the wine carrier role from a specified user.
-   `/update_booze_db` - Updates the carriers in the database from the google spreadsheet
-   `/booze_delete_carrier` - Removes a carrier by XXX-XXX from the boozecarriers table.
-   `/booze_configure_signup_forms` - Updates the google spreadsheet information used by the bot.
-   `/booze_reuse_signup_forms` - Reuses the signup information from last cruise.
-   `/booze_archive_database` - Saves the boozecarriers table to the historical table and clears the boozecarriers table.
-   `/booze_pin_message` - Pins a stat embed by id and adds it to the pinned_messages table to be updated periodically.
-   `/booze_unpin_all` - Removes all the pinned stat messages from the pinned_messages table.
-   `/booze_unpin_message` - Removes a specific pinned stat message from the pinned_messages table by message id.
-   `/booze_timestamp_admin_override` - Sets the start time of the cruise for use in the duration remaining calculation.

### Connoisseur:

-   `/make_wine_carrier` - Gives the wine carrier role from a specified user. (Also has a context menu command)
-   `/booze_tally` - Displays a fun embed of some statistics for the current or a historical cruise.
-   `/booze_tally_extra_stats` - Displays more fun statistics for the current cruise.
-   `/booze_carrier_summary` - Displays how many carriers have unloaded and how many need to unload.

### Wine Carriers:

-   `/wine_carrier_unload <XXX-XXX: str> <planet: str> <market_type: str> <unload_channel: str [optional]>` - Sets an  
    unload notification for the carrier. Notification will be posted into a discord channel if TimedMarket and unload
    channel provided.
-   `/wine_unloading_complete <XXX-XXX: str>` - Marks the carrier unload as completed and deletes the carrier notification.
-   `/find_carriers_with_wine` - Returns an embed with all the remaining wine
-   `/find_wine_carrier_by_id XXX-XXX` - Searches for the carrier XXX-XXX in the database and returns an object
    representing it.
-   `find_wine_carriers_for_platform <platform> <with-wine: bool>` - Returns all the carriers for the platform with
    wine, or all carriers for the platform in total.
-   `/wine_helper_market_open` - Drops an embed into the channel to coordinate unloading.
-   `/wine_helper_market_closed` - Drops an embed into the channel to mark the market as closed.

### General Users

-   `/pirate_steve_help` - Returns information about a specific command
-   `/booze_duration_remaining` -Returns how long the public holiday has left.

# Tech Notes

Run all tests with

```bash
python -m unittest discover
```
