# Changelog

## 1.6.3

- \#311 - Log the carrier causing database update to fail
- \#302 - Sommeliers can’t configure new cruise forms

## 1.6.2

- \#297 - Gate the unload channel harder
- \#293 - Allow sommeliers to archive cruises
- \#291 - When holiday detection fails it returns false

## 1.6.1

- \#286 Move unloads from #announcements to #wine-cellar-unloading

## 1.6.0

- \#281 - Added bot presence
- \#234 - If a new entry is detected, post to let the Sommeliers know
- \#277 - Allow WineCarrier to use find and unload commands

## 1.5.2

- \#269 - Use a new channel for Steve says triggers
- \#255 - Acknowledge simple Hi messages 

## 1.5.1

- \#266 - Updated to support parsing for a user ID in the steve_said message.
  - Steve_Said is now Steve_Says.

## 1.5.0

- \#246 - Updated the 100% reaction
- \#248 - More logging on failure to find carrier during unload
- \#252 - Added new gifs
- \#254 - More gifs
- \#256 - Added steve said command
- \#260 - Help text for steve said

## 1.4.4

- \#241 - More gifs

## 1.4.3

- \#236 - New gifs
- \#232 - Change response user.name to user.display_name for make_wine_carrier
- \#226 - Fleet carrier delete should log back the user

Moar gifs!

## 1.4.2

- \#227 - Sommelier command to toggle Wine Carrier role from a user

## 1.4.1

- \#204 - Add EDO/EDH platform options

## 1.4.0

- \#215 - Signup forms should verify the database is empty first
- \#214 -When nothing in database, return the embed with 0 values
- \#213 - Update allowed resets in the case of timeouts to True
- \#210 - Holiday duration remaining changes
- \#205 - Change Aux and Carrier Owner to the singular role
- \#200 - Restrict find carriers with wine commands to sommelier team
- \#201 - Carriers on multiple trips have the wrong unload notification

## 1.3.0

- \#192 - Archive command needs to stop the polling sheet
- \#190 - Fixed find carriers command
- \#188 - Stop the updating after archive and before new sheet provided
- \#169 - An invalid carrier ID causes the tally commands to fail
- \#177 - Add a text notification in the main channel when an unload starts
- \#179 - Add support for timezone of carriers
- \#175 - Forcefully marking complete should delete any discord notification if it exists
- \#178 - Add time remaining command to the holiday
- \#176 - Forcefully marking as completed shows the wrong embed message

## 1.2.1

- \#170 - Fixed the pinned messages not updating
- \#168 - Fixed some type handling

## 1.2.0

- \#147 - Auto updating pinned embed of stats
- \#159 - Archive should check if the date exists already
- \#158 - Booze bot should allow querying the historical data
- \#68 - Ingest a new form from an admin command
- \#25 - Add historical tracking post-cruise
- \#152 - Remove Statue of Liberty stats, they match the pools
- \#117 - Cast user input carrier IDs to uppercase
- \#118 - Public Holiday system should ping Admins/Mods/Sommeliers/someone
- \#146 - Changed the order of name and ID
- \#162 - For load and unload post the carrier name to the channel when summarizing the command
- \#101 - Align the figures for tally and tally extended
- \#119 - Cant ping roles in an embed

## 1.1.0

- \#139 - Add an else clause to the public_holiday_loop
- \#138 - Check the summation counts match when running extra loads per carrier
- \#136 - Add a squadron only unload option
- \#135 - Add a squadron only unload option

## 1.0.5

- \#124 - Unloading command never populates channel

## 1.0.4

- \#7 - Channel broadcast for when PH starts at HIP 58832
- \#112 - Add logic to remove a carrier

## 1.0.3

- \#106 - Add a help command that dumps data on what the commands do.
- \#105 - Mods should be able to run commands also.
- \#104 - Log and print a message to booze-bot when Pirate Steve connects.
- \#103 - Added /booze_tally_extra_stats command
- \#97 - Add some flavour text to booze tally
- \#94 - Extra logging on database update
- \#93 - Added support for /booze_tally command

## 1.0.2

- \#89 - Release 1.0.2
- \#61 - Fixes Readme file
- \#81 - Make it clearer what roles you need to run the commands
- \#84 - Wrap the database updating into a sub block that is called from other commands
- \#80 - Allow users to check the find_carriers_with_wine command
- \#79 - Find carriers double prints the error message

## 1.0.1

- Load dotenv needs to come before reading values from it
- Bot should log the version
- Grant sommeliers the right to use the helper commands
- Add dotenv as dependency
- Fix setup.py

## 1.0.0

- Database sql dump and DB itself needs to be in a local folder in production
- Add an entry script for the bot
- Change license to non-open source
- Add an update command on production bot
- Add a find command
- Booze bot should return all carriers for the platform 
- Support open for all in carrier unload command
- Add command to mark a carrier unloaded
- Database should track the carriers and whether they are completed or not 
- This interaction failed for wine unload and complete
- Support multiple runs for the same carrier id 
- Carrier ID matching should use a regex check 
- Database population should automatically happen 
- Updated the commands to hold permissions and choice values
- Added requests to the list of dependencies
- Created the public holiday checker
- Tracking for carriers unloading currently
- Fix the embeds for market open and close 
- Cast the carrier-ID to upper case 
- Migrated to use the carrier ID as the unique key
- Track the carriers coming for booze cruise 
- Add command for market closed 
- Fix assassin emoji on test server 
- Add a command that prints a fresh timed market template into chat 
- Added a default booze unloading command 
- Initial structure for connecting to the bot
