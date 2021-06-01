BEGIN TRANSACTION;CREATE TABLE boozecarriers( 
                    entry INTEGER PRIMARY KEY AUTOINCREMENT,
                    carriername TEXT NOT NULL, 
                    carrierid TEXT,
                    winetotal INT,
                    platform TEXT NOT NULL,
                    officialcarrier BOOLEAN,
                    discordusername TEXT NOT NULL,
                    timestamp DATETIME
                );INSERT INTO "boozecarriers" VALUES(1,'Corsair Flagship',NULL,11111,'PC',0,'Avaji#0001',
                '5/31/2021 12:13:18');INSERT INTO "boozecarriers" VALUES(2,'Ignis Vitae J8W-67Q',NULL,20607,'PC',0,'TheNekkbreaker','5/31/2021 12:15:01');INSERT INTO "boozecarriers" VALUES(3,'Star Jumper H4H-G5G (soon PTN Star Jumper etc)',NULL,20000,'PC',1,'jory#7000','5/31/2021 12:24:42');INSERT INTO "boozecarriers" VALUES(4,'Starfleet Operations',NULL,14239,'PC',0,'CMDR Ender Do''Urden','5/31/2021 12:25:50');INSERT INTO "boozecarriers" VALUES(5,'PTN-Trinity',NULL,22320,'PC',1,'Thundachild','5/31/2021 13:35:23');INSERT INTO "boozecarriers" VALUES(6,'P.T.N. Alamo',NULL,18000,'Xbox',1,'AdamC149','5/31/2021 14:18:35');INSERT INTO "boozecarriers" VALUES(7,'Wrenegade (V2Q-NHK)',NULL,15313,'PC',0,'Vertigo#5336 (Nax Wren)','5/31/2021 15:18:10');INSERT INTO "boozecarriers" VALUES(8,'Tomo Sewi',NULL,22000,'PC',0,'palindromordnilap#5586','5/31/2021 16:20:49');INSERT INTO "boozecarriers" VALUES(9,'England''s Glory',NULL,18202,'Xbox',0,'MajorDilligaf','5/31/2021 17:24:19');INSERT INTO "boozecarriers" VALUES(10,'PTN Canadian English',NULL,17212,'PC',1,'root#','5/31/2021 19:26:24');INSERT INTO "boozecarriers" VALUES(11,'Intrusive Goose(H9Q-80W)',NULL,16578,'PC',0,'Root#','5/31/2021 19:30:44');INSERT INTO "boozecarriers" VALUES(12,'P.T.N. Fleet-Chan',NULL,22000,'PC',1,'Vaka_maka#5898','6/1/2021 0:27:58');INSERT INTO "boozecarriers" VALUES(13,'P.T.N. Endurance',NULL,17315,'Xbox',1,'PTN''s Smoked Meat Master','6/1/2021 1:18:21');INSERT INTO "boozecarriers" VALUES(14,'P.T.N. Independence',NULL,21402,'Xbox',1,'PTN''s Smoked Meat Master','6/1/2021 1:20:13');INSERT INTO "boozecarriers" VALUES(15,'The Amborella (KHZ-4XY)',NULL,19000,'PC',0,'CMDR BigfootAUS','6/1/2021 1:27:04');INSERT INTO "boozecarriers" VALUES(16,'Rosinity',NULL,20850,'PC',0,'CapKenty','6/1/2021 1:58:43');DELETE FROM "sqlite_sequence";INSERT INTO "sqlite_sequence" VALUES('boozecarriers',16);COMMIT;