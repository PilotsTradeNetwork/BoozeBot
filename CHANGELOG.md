# Changelog

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
