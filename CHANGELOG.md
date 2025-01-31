# Changelog

## 2.0.7
-    \#494 - Add "Last updated: ..." to pinned tallies (conshmea)
-    \#492 - fix bugs with departures (conshmea)
-    \#491 - Fix carriers being marked as amended when unloading (conshmea)
-    \#490 - Don't update pinned message for historical tallies (conshmea)
-    \#489 - Open/Close WCO Guide with public channels (conshmea)
-    \#488 - Fix DatabaseInteraction errors (IndorilReborn)
-    \#487 - Add controls for departure message posting (IndorilReborn)
-    \#485 - Only ping hitchhikers on the way up, allow N0 blind plot (IndorilReborn)

## 2.0.6

-   \#456 - Added arrow emojis to departure messages
-   \#472 - Purge command no longer runs a db update
-   \#474 - Steve says logs the messages within a codeblock

## 2.0.5

-   \#448 - Handle unformatted departure timestamp
-   \#449 - Convert departure/arrival locations to title case
-   \#450 - Use consistent formatting, remove trailing dot on unload
-   \#460 - Add relative time to booze_duration_remaining
-   \#461 - Return ephemeral responses on departure command
-   \#462 - Send db update embed from background task
-   \#463 - Update steve says commands
-   \#466 - Fix db update numbers
-   \#464 \#467 - Fix /booze_tally not updating the db
-   \#465 - Add purge command
-   \#457 - Steve says command logs to steve-says

## 2.0.4

-   \#436 - Commands respond correctly to IDs not in the database (platform is ignored in BoozeCarrier check)
-   \#435 - Basic error logging added to background tasks
-   \#434 - Departure command no longer says tanker unload in errors
-   Fix loop log messages using old loop timings

## 2.0.3

-   \#426 \#382 - Add commands to view the status of and stop/start the background tasks
-   Fix the tally formatting
-   Decrease the interval between automatically checking the sheet from 1 hour to 10 minutes
-   Added commands to open and close wine carrier feedback
-   Fixed activity status when the cruise channels are open

## 2.0.2

-   \#415 - made b/ping available to somms (as well as council/advisor) (conshmea)
-   \#414 - Updated admin role to be council role OR council advisor (conshmea)
-   \#416 - Fix timestamp missing formatting (conshmea)

## 2.0.1

-   \#409 - Made PH check function async
-   \#408 - Departure message tasks have better error handling
-   \#404 - Booze carrier stats accepts lower case Ids
-   \#403 - Steve says no longer listed as a mod command
-   \#402 - Booze carrier stats no longer shows run total twice
-   Adds httpx as a requirement

## 2.0.0

-   \#344 \#271 - Updates discord.py to version 2.3.1
-   \#271 - Updates discord_slash to discord.py interactions
-   \#383 - /booze_channels_open and /booze_channels_close both return a confirmation embed
-   \#384 - Fix /booze_tally formatting
-   \#388 - Update Cleaner to use role.members instead of guild.members when cleaning roles
-   \#384 - Fixes formatting on booze tally
-   \#390 - Adds command to set the start time (for the duration estimation)
-   \#391 \#155 \##336 - Adds command to reuse the old signup forms
-   \#387 - Add command to list remaining carriers
-   \#383 - Add conformation embed to booze_channels_open
-   \#345 - Update duration remaining to be public
-   \#335 - Update command acknowledges that it happened
-   \#199 - Extended stats updated to have cruise select
-   \#340 - Periodically scans the google sheet (hourly)
-   \#392 \#342 - Adds a command to return the biggest historical cruise tally
-   \#292 - Adds a command to get the stats from a specific carrier
-   \#292 - Add a departure command
-   Signup form no longer requires platform or carrier role sections
-   Improved help command
-   Pirate Steve activity status shows how much wine is tracked when the channels are open
-   Updates README

## 1.8.2

-   \#375 - Fix original permission overwrites being reset by `/booze_channels_open` and `/booze_channels_close`

## 1.8.1

-   \#371 - Make Wine Carrier Click only display output to user and not whole channel

## 1.8.0

-   \#346 - Update description for wine_unload_complete
-   \#354 - Move wine carrier signup notification
-   \#355 - Added Connoisseur to more commands
-   \#362 - Slash descriptions cannot exceed 100 characters

New commands added:

-   \#347 - Remove all wine carriers command - `/clear_booze_roles` - removes Hitchhiker and Wine Carrier roles from all users
-   \#348 - Open/close public channels command - `/booze_channels_open` and `/booze_channels_close` to remove/set the @everyone=False override for viewing public-facing channels
-   \#364 - Separated `/make_wine_carrier` into `/make_wine_carrier` and `/remove_wine_carrier` commands
-   \#365 - New wine carrier welcome message - added `/set_wine_carrier_welcome`, writes user input to a text file `wine_carrier_welcome.txt`
-   \#367 - Context menu command added for making wine carriers
-   All variants of `make_wine_carrier` now send `wine_carrier_welcome.txt` to the wine-carriers-chat channel with a mention for the target user

Command syntax changes:

-   `/make_wine_carrier` obsolete role choice parameter removed

## 1.7.1

-   \#351 - Add permissions for Connoisseurs

Others:

-   Containerized Booze Bot for deployment on portainer

## 1.7.0

-   \#324 - Add wine tanker unload commands
-   \#308 - Add ability to grant wine_tanker role
-   \#321 - Duration remaining should use the timestamp
-   \#307 - Remove PTN Official/Other check
-   \#310 - minor cosmetic change: remove the 'else continue'

New commands added:

-   `/tanker_unload <carrier-id> <system name> <planetary body>` will post up an unloading notification to
    `#tanks-for-the-wine`. For now unloads are cleared with the same command as wine unloads (`/wine_unloading_complete`).
-   Command syntax changes:
-   `/make_wine_carrier` has a new parameter added the role, which has the options for `tanker` or `carrier` to grant
    the necessary discord roles.

Others:

-   Duration remaining should now provide a user time zone friendly response.

## 1.6.4

-   \#316 - Fix database update to use carrier ID as unique constraint

## 1.6.3

-   \#311 - Log the carrier causing database update to fail
-   \#302 - Sommeliers can’t configure new cruise forms

## 1.6.2

-   \#297 - Gate the unload channel harder
-   \#293 - Allow sommeliers to archive cruises
-   \#291 - When holiday detection fails it returns false

## 1.6.1

-   \#286 Move unloads from #announcements to #wine-cellar-unloading

## 1.6.0

-   \#281 - Added bot presence
-   \#234 - If a new entry is detected, post to let the Sommeliers know
-   \#277 - Allow WineCarrier to use find and unload commands

## 1.5.2

-   \#269 - Use a new channel for Steve says triggers
-   \#255 - Acknowledge simple Hi messages

## 1.5.1

-   \#266 - Updated to support parsing for a user ID in the steve_said message.
    -   Steve_Said is now Steve_Says.

## 1.5.0

-   \#246 - Updated the 100% reaction
-   \#248 - More logging on failure to find carrier during unload
-   \#252 - Added new gifs
-   \#254 - More gifs
-   \#256 - Added steve said command
-   \#260 - Help text for steve said

## 1.4.4

-   \#241 - More gifs

## 1.4.3

-   \#236 - New gifs
-   \#232 - Change response user.name to user.display_name for make_wine_carrier
-   \#226 - Fleet carrier delete should log back the user

Moar gifs!

## 1.4.2

-   \#227 - Sommelier command to toggle Wine Carrier role from a user

## 1.4.1

-   \#204 - Add EDO/EDH platform options

## 1.4.0

-   \#215 - Signup forms should verify the database is empty first
-   \#214 -When nothing in database, return the embed with 0 values
-   \#213 - Update allowed resets in the case of timeouts to True
-   \#210 - Holiday duration remaining changes
-   \#205 - Change Aux and Carrier Owner to the singular role
-   \#200 - Restrict find carriers with wine commands to sommelier team
-   \#201 - Carriers on multiple trips have the wrong unload notification

## 1.3.0

-   \#192 - Archive command needs to stop the polling sheet
-   \#190 - Fixed find carriers command
-   \#188 - Stop the updating after archive and before new sheet provided
-   \#169 - An invalid carrier ID causes the tally commands to fail
-   \#177 - Add a text notification in the main channel when an unload starts
-   \#179 - Add support for timezone of carriers
-   \#175 - Forcefully marking complete should delete any discord notification if it exists
-   \#178 - Add time remaining command to the holiday
-   \#176 - Forcefully marking as completed shows the wrong embed message

## 1.2.1

-   \#170 - Fixed the pinned messages not updating
-   \#168 - Fixed some type handling

## 1.2.0

-   \#147 - Auto updating pinned embed of stats
-   \#159 - Archive should check if the date exists already
-   \#158 - Booze bot should allow querying the historical data
-   \#68 - Ingest a new form from an admin command
-   \#25 - Add historical tracking post-cruise
-   \#152 - Remove Statue of Liberty stats, they match the pools
-   \#117 - Cast user input carrier IDs to uppercase
-   \#118 - Public Holiday system should ping Admins/Mods/Sommeliers/someone
-   \#146 - Changed the order of name and ID
-   \#162 - For load and unload post the carrier name to the channel when summarizing the command
-   \#101 - Align the figures for tally and tally extended
-   \#119 - Cant ping roles in an embed

## 1.1.0

-   \#139 - Add an else clause to the public_holiday_loop
-   \#138 - Check the summation counts match when running extra loads per carrier
-   \#136 - Add a squadron only unload option
-   \#135 - Add a squadron only unload option

## 1.0.5

-   \#124 - Unloading command never populates channel

## 1.0.4

-   \#7 - Channel broadcast for when PH starts at HIP 58832
-   \#112 - Add logic to remove a carrier

## 1.0.3

-   \#106 - Add a help command that dumps data on what the commands do.
-   \#105 - Mods should be able to run commands also.
-   \#104 - Log and print a message to booze-bot when Pirate Steve connects.
-   \#103 - Added /booze_tally_extra_stats command
-   \#97 - Add some flavour text to booze tally
-   \#94 - Extra logging on database update
-   \#93 - Added support for /booze_tally command

## 1.0.2

-   \#89 - Release 1.0.2
-   \#61 - Fixes Readme file
-   \#81 - Make it clearer what roles you need to run the commands
-   \#84 - Wrap the database updating into a sub block that is called from other commands
-   \#80 - Allow users to check the find_carriers_with_wine command
-   \#79 - Find carriers double prints the error message

## 1.0.1

-   Load dotenv needs to come before reading values from it
-   Bot should log the version
-   Grant sommeliers the right to use the helper commands
-   Add dotenv as dependency
-   Fix setup.py

## 1.0.0

-   Database sql dump and DB itself needs to be in a local folder in production
-   Add an entry script for the bot
-   Change license to non-open source
-   Add an update command on production bot
-   Add a find command
-   Booze bot should return all carriers for the platform
-   Support open for all in carrier unload command
-   Add command to mark a carrier unloaded
-   Database should track the carriers and whether they are completed or not
-   This interaction failed for wine unload and complete
-   Support multiple runs for the same carrier id
-   Carrier ID matching should use a regex check
-   Database population should automatically happen
-   Updated the commands to hold permissions and choice values
-   Added requests to the list of dependencies
-   Created the public holiday checker
-   Tracking for carriers unloading currently
-   Fix the embeds for market open and close
-   Cast the carrier-ID to upper case
-   Migrated to use the carrier ID as the unique key
-   Track the carriers coming for booze cruise
-   Add command for market closed
-   Fix assassin emoji on test server
-   Add a command that prints a fresh timed market template into chat
-   Added a default booze unloading command
-   Initial structure for connecting to the bot
