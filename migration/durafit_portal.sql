-- MySQL dump 10.13  Distrib 8.0.39, for Win64 (x86_64)
--
-- Host: localhost    Database: durafit_portal
-- ------------------------------------------------------
-- Server version	8.0.39

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `durafit_portal`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `durafit_portal` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `durafit_portal`;

--
-- Table structure for table `portal_cases`
--

DROP TABLE IF EXISTS `portal_cases`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_cases` (
  `case_id` varchar(40) NOT NULL,
  `submission_id` binary(16) NOT NULL,
  `crm_order_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `case_status` varchar(32) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `closed_at` datetime(6) DEFAULT NULL,
  `assigned_to` varchar(255) DEFAULT NULL,
  `priority` varchar(32) DEFAULT NULL,
  `internal_notes` text,
  PRIMARY KEY (`case_id`),
  UNIQUE KEY `submission_id` (`submission_id`),
  KEY `ix_portal_cases_crm_order_created` (`crm_order_id`,`created_at`),
  KEY `ix_portal_cases_status_created` (`case_status`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_cases`
--

LOCK TABLES `portal_cases` WRITE;
/*!40000 ALTER TABLE `portal_cases` DISABLE KEYS */;
INSERT INTO `portal_cases` VALUES ('DF91-CASE-20260917-05C8',_binary '«A:wAÙ€\Ò\÷\Ít¾','02XVWZXVD14L','received','2026-09-17 12:57:04.673455','2026-09-17 12:57:04.673455',NULL,NULL,NULL,NULL),('DF91-CASE-20260917-94FA',_binary '©‹Hú«GÍ¢ú¼gp','02XVWZXVD14L','received','2026-09-17 12:39:34.150379','2026-09-17 12:39:34.150379',NULL,NULL,NULL,NULL),('DF91-CASE-20260917-C7A9',_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','02XVWZXVD14L','received','2026-09-17 12:38:48.183629','2026-09-17 12:38:48.183629',NULL,NULL,NULL,NULL),('DF91-CASE-20260917-EEAA',_binary 'P”\Ê\öK†–Ã²\ãZ]','OD337969604263136100','received','2026-09-17 13:27:59.498035','2026-09-17 13:27:59.498035',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-07B0',_binary '_j¥”\ôCË»\æ\ò\Ä\íRÕ¤',NULL,'received','2026-09-18 10:25:39.876820','2026-09-18 10:25:39.876820',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-2CDD',_binary 'N’ˆ¨KL\æ›ø\ØøN\ÇS',NULL,'received','2026-09-18 10:13:13.115200','2026-09-18 10:13:13.115200',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-3894',_binary '¢]~tm¿Hš“\å!–_D',NULL,'received','2026-09-18 10:36:44.777655','2026-09-18 10:36:44.777655',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-46C0',_binary '\ä”0ª¿H·	\ëzŠ¤\Í',NULL,'received','2026-09-18 10:35:30.569226','2026-09-18 10:35:30.569226',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-49D2',_binary 'ş8ø\Ê9>F-£—r—Š‰ü','402-2057639-2251544','received','2026-09-18 10:25:31.517310','2026-09-18 10:25:31.517310',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-4FB6',_binary 'ş˜„\î\Ì\"@½«/‘®|¢',NULL,'received','2026-09-18 10:35:11.903303','2026-09-18 10:35:11.903303',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-93BD',_binary ' ¾\ÇnH1’Q`ç§¬¿',NULL,'received','2026-09-18 10:25:17.427449','2026-09-18 10:25:17.427449',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-9A36',_binary '\İü$\ĞXL{±¡\Ú\è‚I~E',NULL,'received','2026-09-18 10:18:18.094740','2026-09-18 10:18:18.094740',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-B353',_binary '¨Q3®ZD\ñ\öE\àBI¡',NULL,'received','2026-09-18 10:32:49.134341','2026-09-18 10:32:49.134341',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-BFF5',_binary '˜\ÉNş³C—¹\æoşˆ³',NULL,'received','2026-09-18 10:18:47.007427','2026-09-18 10:18:47.007427',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-C4A9',_binary 'w3­–¾\×O®¼—švÿzù¶',NULL,'received','2026-09-18 10:13:34.028082','2026-09-18 10:13:34.028082',NULL,NULL,NULL,NULL),('DF91-CASE-20260918-D5D3',_binary '\Z?½\'‹vO\åŸjş[\ğº','OD436832864263801100','received','2026-09-18 07:22:58.517614','2026-09-18 07:22:58.517614',NULL,NULL,NULL,NULL),('DF91-CASE-20260920-03A1',_binary '{\ZIMª¬gªe\Í\÷\Ê',NULL,'received','2026-09-19 19:45:46.180273','2026-09-19 19:45:46.180273',NULL,NULL,NULL,NULL),('DF91-CASE-20260920-1948',_binary '³b\ä0¢\nEÎ‹s¸‘l\Æ',NULL,'received','2026-09-19 19:38:24.302124','2026-09-19 19:38:24.302124',NULL,NULL,NULL,NULL),('DF91-CASE-20260920-B665',_binary 'ü5_>_\ò@\'“\æ\ì\ÊLš',NULL,'received','2026-09-19 19:44:59.152524','2026-09-19 19:44:59.152524',NULL,NULL,NULL,NULL),('DF91-CASE-20260920-C92A',_binary 'y\ÍNÿş#AÎ‘\Z^k¬\Ü\r±',NULL,'received','2026-09-19 19:44:58.113954','2026-09-19 19:44:58.113954',NULL,NULL,NULL,NULL),('DF91-CASE-20260920-D307',_binary 'ùÅš\Ç.\Ö@o°\ØIÄ\àº@','OD438366685731028100','received','2026-09-19 19:32:59.587661','2026-09-19 19:32:59.587661',NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `portal_cases` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portal_email_outbox`
--

DROP TABLE IF EXISTS `portal_email_outbox`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_email_outbox` (
  `outbox_id` binary(16) NOT NULL,
  `submission_id` binary(16) NOT NULL,
  `message_type` varchar(64) NOT NULL,
  `delivery_status` varchar(32) NOT NULL,
  `attempt_count` int unsigned NOT NULL DEFAULT '0',
  `next_attempt_at` datetime(6) DEFAULT NULL,
  `sent_at` datetime(6) DEFAULT NULL,
  `provider_message_id` varchar(255) DEFAULT NULL,
  `last_error` text,
  PRIMARY KEY (`outbox_id`),
  UNIQUE KEY `ux_portal_outbox_submission_message` (`submission_id`,`message_type`),
  KEY `ix_portal_outbox_status_next_attempt` (`delivery_status`,`next_attempt_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_email_outbox`
--

LOCK TABLES `portal_email_outbox` WRITE;
/*!40000 ALTER TABLE `portal_email_outbox` DISABLE KEYS */;
INSERT INTO `portal_email_outbox` VALUES (_binary '\Ê%6\Ô3Gp™\ÄE\Ä\Ì\ğº',_binary '¨Q3®ZD\ñ\öE\àBI¡','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '±Ò»˜´F‘»z{h8Iş',_binary '\ä”0ª¿H·	\ëzŠ¤\Í','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary ')-Û¬\ÄO«¾5%m\âb',_binary 'ü5_>_\ò@\'“\æ\ì\ÊLš','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '2Z\ÎL©1AT¤:ZO¸ß’',_binary 'y\ÍNÿş#AÎ‘\Z^k¬\Ü\r±','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary ';ú8©CÈ±-¤ÿt­',_binary 'ùÅš\Ç.\Ö@o°\ØIÄ\àº@','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'A\êBf@ƒ¯\ÎCIuP®',_binary '\Z?½\'‹vO\åŸjş[\ğº','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'cx—·WHøŒ¬SAÂ\ì',_binary '«A:wAÙ€\Ò\÷\Ít¾','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'cı\ó¡mB¯ƒ,.[ÿœS',_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'u®\Ü\Ó\è+H¶?‚‘=\æ\ï\Ğ',_binary '¢]~tm¿Hš“\å!–_D','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'a\áŸGª†ƒK\ñ[\ö',_binary 'N’ˆ¨KL\æ›ø\ØøN\ÇS','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '¦™¯\ÈE‹“%\ñ_Gc»',_binary 'ş˜„\î\Ì\"@½«/‘®|¢','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'ŸÑ˜³\ÌI³6I\ß\0\nş',_binary '˜\ÉNş³C—¹\æoşˆ³','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '¨h\Øm¢A~·§\\\ì\Ù\ğü\Ô',_binary '©‹Hú«GÍ¢ú¼gp','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '¬\Ù\ò²\æ3Jv‰k©¥$Hÿ@',_binary 'w3­–¾\×O®¼—švÿzù¶','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary 'µ5„\Õ|]K¡ ¦Heƒ	“Š',_binary '_j¥”\ôCË»\æ\ò\Ä\íRÕ¤','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '¶¿n}wAR·AØ±\î\É\å',_binary ' ¾\ÇnH1’Q`ç§¬¿','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '\Ä\áde³ÀFÈ‹\õF\ê7\Ø',_binary '{\ZIMª¬gªe\Í\÷\Ê','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '\É\Ê:M\ÈIš~)8—¤/¶',_binary 'P”\Ê\öK†–Ã²\ãZ]','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '\ÎhSQJaœÿD0\ê´6T',_binary '³b\ä0¢\nEÎ‹s¸‘l\Æ','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '\Ñ\íP\Ë\ÅFÍ›µ[G¸]\ßa',_binary '\İü$\ĞXL{±¡\Ú\è‚I~E','customer_confirmation','pending',0,NULL,NULL,NULL,NULL),(_binary '\í\÷“¬UFL·Î„u½[cw',_binary 'ş8ø\Ê9>F-£—r—Š‰ü','customer_confirmation','pending',0,NULL,NULL,NULL,NULL);
/*!40000 ALTER TABLE `portal_email_outbox` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portal_import_history`
--

DROP TABLE IF EXISTS `portal_import_history`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_import_history` (
  `import_id` binary(16) NOT NULL,
  `import_type` varchar(16) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `started_at` datetime(6) NOT NULL,
  `completed_at` datetime(6) DEFAULT NULL,
  `total_rows` int unsigned NOT NULL DEFAULT '0',
  `inserted_rows` int unsigned NOT NULL DEFAULT '0',
  `skipped_rows` int unsigned NOT NULL DEFAULT '0',
  `failed_rows` int unsigned NOT NULL DEFAULT '0',
  `status` varchar(32) NOT NULL,
  `error_summary` text,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`import_id`),
  KEY `ix_portal_import_history_type_created` (`import_type`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_import_history`
--

LOCK TABLES `portal_import_history` WRITE;
/*!40000 ALTER TABLE `portal_import_history` DISABLE KEYS */;
INSERT INTO `portal_import_history` VALUES (_binary 'RÁ%=«J\ë¯+\Ğ{5ƒ-','cases','test-cases.xlsx','2026-09-18 05:06:16.684346','2026-09-18 05:06:16.753101',2,2,0,0,'completed',NULL,'2026-09-18 05:06:16.684346'),(_binary 'a(\é\×Fü¼\ï×©\ä8;','cases','test-cases.xlsx','2026-09-18 05:20:18.745010','2026-09-18 05:20:18.807332',2,0,2,0,'completed',NULL,'2026-09-18 05:20:18.745010'),(_binary '\Ât\ÃC\÷XŠÁ¿\Ğ','crm','test-crm.xlsx','2026-09-18 10:25:34.590834','2026-09-18 10:25:34.649654',2,1,1,0,'completed',NULL,'2026-09-18 10:25:34.590834'),(_binary '\rh±$rAÒŒaÀ/üø','crm','test-crm.xlsx','2026-09-18 05:06:16.933114','2026-09-18 05:06:17.021076',2,1,1,0,'completed',NULL,'2026-09-18 05:06:16.933114'),(_binary 'ai˜°\ßHf‰š\÷—m\Ğ\Ú','crm','test-crm.xlsx','2026-09-18 05:06:49.184155','2026-09-18 05:06:49.237282',2,1,1,0,'completed',NULL,'2026-09-18 05:06:49.184155'),(_binary '¨gşMG\÷Œ=³y\æ','crm','test-crm.xlsx','2026-09-18 05:06:17.038576','2026-09-18 05:06:17.132311',2,0,2,0,'completed',NULL,'2026-09-18 05:06:17.038576'),(_binary '\æŸ~K·¹\ô\Ü&\ÎÆ‚Z','crm','test-crm.xlsx','2026-09-18 08:26:45.498396','2026-09-18 08:26:45.709474',2,0,2,0,'completed',NULL,'2026-09-18 08:26:45.498396'),(_binary '€¨2H~„\÷úSİ„','crm','test-crm.xlsx','2026-09-18 09:55:23.647384','2026-09-18 09:55:23.717825',2,1,1,0,'completed',NULL,'2026-09-18 09:55:23.647384'),(_binary '\Z±\èC„°HÙ©¶iº˜É¼','cases','test-cases.xlsx','2026-09-18 10:13:11.097383','2026-09-18 10:13:11.145543',2,0,2,0,'completed',NULL,'2026-09-18 10:13:11.097383'),(_binary '½)\Éc¥HD¦ıC$T”','crm','test-crm.xlsx','2026-09-18 05:48:14.493228','2026-09-18 05:48:14.591134',2,1,1,0,'completed',NULL,'2026-09-18 05:48:14.493228'),(_binary 'U8G‹¶#\äÍ\ò','crm','test-crm.xlsx','2026-09-18 10:18:45.407687','2026-09-18 10:18:45.462546',2,0,2,0,'completed',NULL,'2026-09-18 10:18:45.407687'),(_binary '#s\æ\èW@)ª\ö\ğ[[™V','cases','test-cases.xlsx','2026-09-18 10:18:45.140354','2026-09-18 10:18:45.189988',2,0,2,0,'completed',NULL,'2026-09-18 10:18:45.140354'),(_binary '$ª7\íŞ©A\÷“9\×4ˆ¨%\ô','cases','test-cases.xlsx','2026-09-18 05:48:14.175938','2026-09-18 05:48:14.257360',2,2,0,0,'completed',NULL,'2026-09-18 05:48:14.175938'),(_binary '(t]\ÅL¸‘\Ëó¦½›©ø','crm','test-crm.xlsx','2026-09-18 05:07:42.451182','2026-09-18 05:07:42.532137',2,0,2,0,'completed',NULL,'2026-09-18 05:07:42.451182'),(_binary '+Û’…ƒM³®7*\÷)¼','crm','test-crm.xlsx','2026-09-18 10:13:32.234161','2026-09-18 10:13:32.295074',2,1,1,0,'completed',NULL,'2026-09-18 10:13:32.234161'),(_binary '1´,O–ŠOM¬»ƒ\Æ\Ó\î¢','crm','test-crm.xlsx','2026-09-18 08:26:45.254164','2026-09-18 08:26:45.472583',2,1,1,0,'completed',NULL,'2026-09-18 08:26:45.254164'),(_binary '2iŞüZJ\Z«Y\å[E¡L','cases','test-cases.xlsx','2026-09-18 05:06:16.767550','2026-09-18 05:06:16.853145',2,0,2,0,'completed',NULL,'2026-09-18 05:06:16.767550'),(_binary '2z#j]FV‘ı\0µÈ½\ã\õ','crm','test-crm.xlsx','2026-09-18 07:56:06.394047','2026-09-18 07:56:06.512394',2,1,1,0,'completed',NULL,'2026-09-18 07:56:06.394047'),(_binary '2¸†FSIıŸ\Õ\Í$/\Äi','crm','test-crm.xlsx','2026-09-18 05:05:47.830319','2026-09-18 05:05:47.884940',2,0,2,0,'completed',NULL,'2026-09-18 05:05:47.830319'),(_binary '3\á˜{vU@Ê’\å=\å…V','cases','test-cases.xlsx','2026-09-18 05:06:49.064608','2026-09-18 05:06:49.121483',2,0,2,0,'completed',NULL,'2026-09-18 05:06:49.064608'),(_binary '4X\ä\ôX¬KC¥Ú—ûa\Ü','cases','test-cases.xlsx','2026-09-18 10:25:34.313825','2026-09-18 10:25:34.361309',2,0,2,0,'completed',NULL,'2026-09-18 10:25:34.313825'),(_binary '5\ğ\r~É‚O\"—\ôv$»\ê\Ğ','crm','test-crm.xlsx','2026-09-18 07:46:34.365715','2026-09-18 07:46:34.466440',2,1,1,0,'completed',NULL,'2026-09-18 07:46:34.365715'),(_binary '5ø\ÜjxN‡‰c¬Šúy®','crm','test-crm.xlsx','2026-09-18 06:18:40.319692','2026-09-18 06:18:40.514137',2,0,2,0,'completed',NULL,'2026-09-18 06:18:40.319692'),(_binary '7¢\ç\ö\÷M0¹\İVj<\Ï\è','cases','test-cases.xlsx','2026-09-18 05:07:42.061572','2026-09-18 05:07:42.129142',2,2,0,0,'completed',NULL,'2026-09-18 05:07:42.061572'),(_binary '8¹k ¹L¡¡¿ƒÿ\à†O ','crm','test-crm.xlsx','2026-09-18 05:48:14.607867','2026-09-18 05:48:14.673743',2,0,2,0,'completed',NULL,'2026-09-18 05:48:14.607867'),(_binary '@DŒ+\ÊE—)0{\ö\0>','cases','test-cases.xlsx','2026-09-18 10:02:23.872744','2026-09-18 10:02:23.937076',2,2,0,0,'completed',NULL,'2026-09-18 10:02:23.872744'),(_binary 'AaO[E\ÂFU©~k‹‚x¡¶','crm','test-crm.xlsx','2026-09-18 09:31:47.533796','2026-09-18 09:31:47.601320',2,1,1,0,'completed',NULL,'2026-09-18 09:31:47.533796'),(_binary 'C1IcO\ôµ\Óü\Æ\Ç\İm','cases','test-cases.xlsx','2026-09-18 10:02:23.953705','2026-09-18 10:02:24.003869',2,0,2,0,'completed',NULL,'2026-09-18 10:02:23.953705'),(_binary 'CF\ä<›ªG¾šÉ¾bÄ ¶\÷','crm','test-crm.xlsx','2026-09-18 06:07:59.091555','2026-09-18 06:07:59.180191',2,1,1,0,'completed',NULL,'2026-09-18 06:07:59.091555'),(_binary 'C\ÈU \ï¤C“®¼‡\às%h','cases','test-cases.xlsx','2026-09-18 07:46:53.066349','2026-09-18 07:46:53.148035',2,0,2,0,'completed',NULL,'2026-09-18 07:46:53.066349'),(_binary 'D@R›\à\ğMê¶Œ~,¼y','cases','test-cases.xlsx','2026-09-18 05:07:42.142526','2026-09-18 05:07:42.244349',2,0,2,0,'completed',NULL,'2026-09-18 05:07:42.142526'),(_binary 'G2\"SÖŸA´‹\ÃPe\õ° ','crm','test-crm.xlsx','2026-09-18 10:13:11.312689','2026-09-18 10:13:11.378770',2,1,1,0,'completed',NULL,'2026-09-18 10:13:11.312689'),(_binary 'J\×n\âT\æHÌ³‹ş\í\Ã/\ò\\','crm','test-crm.xlsx','2026-09-18 05:07:42.340009','2026-09-18 05:07:42.430675',2,1,1,0,'completed',NULL,'2026-09-18 05:07:42.340009'),(_binary 'K\í\Z[šI›±@\çÂ¤\ÅB\ö','cases','test-cases.xlsx','2026-09-18 06:07:27.036535','2026-09-18 06:07:27.133608',2,2,0,0,'completed',NULL,'2026-09-18 06:07:27.036535'),(_binary 'L•#\ğg\ÏAÿ¥`\ñ\×äº˜','cases','test-cases.xlsx','2026-09-18 10:13:32.014545','2026-09-18 10:13:32.061083',2,0,2,0,'completed',NULL,'2026-09-18 10:13:32.014545'),(_binary 'QšY\ŞÀHD“G.P!\Î,®','crm','test-crm.xlsx','2026-09-18 10:18:45.340762','2026-09-18 10:18:45.390358',2,1,1,0,'completed',NULL,'2026-09-18 10:18:45.340762'),(_binary 'S(™6\ò@Ü“«mWˆ$','cases','test-cases.xlsx','2026-09-18 05:05:47.476519','2026-09-18 05:05:47.578416',2,0,2,0,'completed',NULL,'2026-09-18 05:05:47.476519'),(_binary 'V{\æ~”G­‹Ë²=–ø†´','crm','test-crm.xlsx','2026-09-18 10:25:34.662650','2026-09-18 10:25:34.725168',2,0,2,0,'completed',NULL,'2026-09-18 10:25:34.662650'),(_binary 'Vq‰KB{”M¬\Êşı\õ','cases','test-cases.xlsx','2026-09-18 06:18:39.738653','2026-09-18 06:18:39.832559',2,0,2,0,'completed',NULL,'2026-09-18 06:18:39.738653'),(_binary '^\Õ½¦TC‚¤\ÈS¶h*I','crm','test-crm.xlsx','2026-09-18 05:06:49.267126','2026-09-18 05:06:49.317620',2,0,2,0,'completed',NULL,'2026-09-18 05:06:49.267126'),(_binary '_’7S¨¸D¬§š´?4ua','cases','test-cases.xlsx','2026-09-18 07:46:33.618052','2026-09-18 07:46:33.974751',2,2,0,0,'completed',NULL,'2026-09-18 07:46:33.618052'),(_binary 'cgL~•\Î\Î9Á\Ë','cases','test-cases.xlsx','2026-09-18 09:31:47.332468','2026-09-18 09:31:47.381920',2,0,2,0,'completed',NULL,'2026-09-18 09:31:47.332468'),(_binary 'h}·\Ñ\ñJ×³iOüS¬','cases','test-cases.xlsx','2026-09-18 06:07:27.147237','2026-09-18 06:07:27.212458',2,0,2,0,'completed',NULL,'2026-09-18 06:07:27.147237'),(_binary 'jùE,\İ[IJ…¢\ö½\ğè±€','cases','test-cases.xlsx','2026-09-18 10:18:45.076875','2026-09-18 10:18:45.124667',2,2,0,0,'completed',NULL,'2026-09-18 10:18:45.076875'),(_binary 'ks[—A]˜Ÿ±$\õ(','cases','test-cases.xlsx','2026-09-18 07:46:52.780834','2026-09-18 07:46:53.046720',2,2,0,0,'completed',NULL,'2026-09-18 07:46:52.780834'),(_binary 'kÁ[J>§J¨˜\nEù£²™','crm','test-crm.xlsx','2026-09-18 09:55:23.729907','2026-09-18 09:55:23.785853',2,0,2,0,'completed',NULL,'2026-09-18 09:55:23.729907'),(_binary 'laI¾•\ïN‚\ç\\\Ã\ĞD76','cases','test-cases.xlsx','2026-09-18 08:26:43.881031','2026-09-18 08:26:44.107723',2,2,0,0,'completed',NULL,'2026-09-18 08:26:43.881031'),(_binary 'züÿP@C…£\Ì	q\ê\Ì\õ9','cases','test-cases.xlsx','2026-09-18 09:55:23.427342','2026-09-18 09:55:23.479683',2,0,2,0,'completed',NULL,'2026-09-18 09:55:23.427342'),(_binary '{\ë\Û\ïœ\åA\n¤\äVE`sÿ','cases','test-cases.xlsx','2026-09-18 10:25:34.250281','2026-09-18 10:25:34.298184',2,2,0,0,'completed',NULL,'2026-09-18 10:25:34.250281'),(_binary 'ƒg\ÖÆ™EO•†mT£;m\0','cases','test-cases.xlsx','2026-09-18 08:26:44.137672','2026-09-18 08:26:44.325768',2,0,2,0,'completed',NULL,'2026-09-18 08:26:44.137672'),(_binary '†¼“—Ä–H\äš\ä\ß7:.‚+','cases','test-cases.xlsx','2026-09-18 07:56:05.741284','2026-09-18 07:56:05.945897',2,2,0,0,'completed',NULL,'2026-09-18 07:56:05.741284'),(_binary '‰\ÔV)¨­EŒŒÜ£iÿ±)','cases','Cases-20-09-2026.xlsx','2026-09-19 19:28:41.538348','2026-09-19 19:29:01.970660',9027,154,8873,0,'completed',NULL,'2026-09-19 19:28:41.538348'),(_binary '\÷7×½ÿD3ª \Ùg4\İ','crm','test-crm.xlsx','2026-09-18 06:07:59.198488','2026-09-18 06:07:59.263217',2,0,2,0,'completed',NULL,'2026-09-18 06:07:59.198488'),(_binary 'Ÿx\ÊMxD­·mx€;','crm','test-crm.xlsx','2026-09-18 09:31:47.616430','2026-09-18 09:31:47.665451',2,0,2,0,'completed',NULL,'2026-09-18 09:31:47.616430'),(_binary '¡!ƒ\î\å‡K§¡É­¶\è<¢','crm','test-crm.xlsx','2026-09-18 05:05:47.668369','2026-09-18 05:05:47.807356',2,1,1,0,'completed',NULL,'2026-09-18 05:05:47.668369'),(_binary '¦¡\ÛşKÚŸš¨-¤µ)','cases','test-cases.xlsx','2026-09-18 07:56:05.982427','2026-09-18 07:56:06.113322',2,0,2,0,'completed',NULL,'2026-09-18 07:56:05.982427'),(_binary 'ª\Ë zc/A/»tMP2\ó','crm','test-crm.xlsx','2026-09-18 07:46:53.430502','2026-09-18 07:46:53.514326',2,1,1,0,'completed',NULL,'2026-09-18 07:46:53.430502'),(_binary '¬3oË¯F4€hQHY','cases','test-cases.xlsx','2026-09-18 06:07:58.881523','2026-09-18 06:07:58.981881',2,0,2,0,'completed',NULL,'2026-09-18 06:07:58.881523'),(_binary '­%x\Í\'\ÜL‹½sÏ«\ë\Ç3','cases','test-cases.xlsx','2026-09-18 07:46:33.999245','2026-09-18 07:46:34.098025',2,0,2,0,'completed',NULL,'2026-09-18 07:46:33.999245'),(_binary '­«^\Ì\ÛSMt£+`šÍ¦\r','cases','test-cases.xlsx','2026-09-18 05:20:18.632586','2026-09-18 05:20:18.712081',2,2,0,0,'completed',NULL,'2026-09-18 05:20:18.632586'),(_binary '²dw•A\n¡\r8\öÁ™','cases','test-cases.xlsx','2026-09-18 06:18:39.626272','2026-09-18 06:18:39.725936',2,2,0,0,'completed',NULL,'2026-09-18 06:18:39.626272'),(_binary '¾®¼œ¸MK½¿W0P]“\Ã','crm','_CRM Master_Live (2).xlsx','2026-09-18 06:26:30.174797','2026-09-18 06:28:15.523783',17382,306,17076,0,'completed',NULL,'2026-09-18 06:26:30.174797'),(_binary 'ÀÅ³tü)O\ãƒ\ÎCš54À)','crm','test-crm.xlsx','2026-09-18 06:18:40.195655','2026-09-18 06:18:40.290542',2,1,1,0,'completed',NULL,'2026-09-18 06:18:40.195655'),(_binary 'Á\ğŒGš¼0&G~','cases','test-cases.xlsx','2026-09-18 10:13:11.032054','2026-09-18 10:13:11.095365',2,2,0,0,'completed',NULL,'2026-09-18 10:13:11.032054'),(_binary 'Ç±\Ó\ò#¥F\r˜s”¢ú&','crm','test-crm.xlsx','2026-09-18 10:13:11.378770','2026-09-18 10:13:11.446509',2,0,2,0,'completed',NULL,'2026-09-18 10:13:11.378770'),(_binary '\Çü\èCUnL\'‡\È\Z\Ê\æ´','cases','test-cases.xlsx','2026-09-18 09:31:47.262208','2026-09-18 09:31:47.313852',2,2,0,0,'completed',NULL,'2026-09-18 09:31:47.262208'),(_binary '\Ë\ZvR—wC1©s«(´²^ú','crm','test-crm.xlsx','2026-09-18 07:46:53.546737','2026-09-18 07:46:53.637678',2,0,2,0,'completed',NULL,'2026-09-18 07:46:53.546737'),(_binary '\ÌHÏGB°5DG\Æµ','crm','test-crm.xlsx','2026-09-18 07:46:34.492327','2026-09-18 07:46:34.567370',2,0,2,0,'completed',NULL,'2026-09-18 07:46:34.492327'),(_binary 'Ô¢D)úûO\ì’\Ê/§«‰v','cases','test-cases.xlsx','2026-09-18 05:05:47.348827','2026-09-18 05:05:47.449736',2,2,0,0,'completed',NULL,'2026-09-18 05:05:47.348827'),(_binary '\Õ\\\à\á\åDÆ\İ\Z¦%f¦','cases','test-cases.xlsx','2026-09-18 10:18:16.225326','2026-09-18 10:18:16.258521',2,0,2,0,'completed',NULL,'2026-09-18 10:18:16.225326'),(_binary '\Ù\Éi\Ì\İ4D¦{—\İ9\ôDš','cases','test-cases.xlsx','2026-09-18 06:07:58.746693','2026-09-18 06:07:58.830994',2,2,0,0,'completed',NULL,'2026-09-18 06:07:58.746693'),(_binary '\İwa«LÖ¥•… › t.','cases','test-cases.xlsx','2026-09-18 10:13:31.911827','2026-09-18 10:13:31.991312',2,2,0,0,'completed',NULL,'2026-09-18 10:13:31.911827'),(_binary '\á$sv†SG=”OÚ¾__›','crm','test-crm.xlsx','2026-09-18 10:02:24.299772','2026-09-18 10:02:24.350378',2,0,2,0,'completed',NULL,'2026-09-18 10:02:24.299772'),(_binary '\áe?¯ZA§¨q<Ñ¿\ö','crm','test-crm.xlsx','2026-09-18 08:28:22.819846','2026-09-18 08:28:23.059253',2,0,2,0,'completed',NULL,'2026-09-18 08:28:22.819846'),(_binary '\ãH²Ÿ‰\áCJ€ÿ:2\Ä\×Î„','cases','test-cases.xlsx','2026-09-18 10:18:16.141189','2026-09-18 10:18:16.206919',2,2,0,0,'completed',NULL,'2026-09-18 10:18:16.141189'),(_binary '\åJß„À\Û@œ“#Hº‚4 \Í','cases','test-cases.xlsx','2026-09-18 05:48:14.285001','2026-09-18 05:48:14.376266',2,0,2,0,'completed',NULL,'2026-09-18 05:48:14.285001'),(_binary '\é	Lbw`F1”\ã\ïv\Ñ1','cases','test-cases.xlsx','2026-09-18 05:06:48.978570','2026-09-18 05:06:49.048313',2,2,0,0,'completed',NULL,'2026-09-18 05:06:48.978570'),(_binary '\ê2l¾<N:·Q\Ú\èS\Î','crm','test-crm.xlsx','2026-09-18 10:13:32.319788','2026-09-18 10:13:32.377963',2,0,2,0,'completed',NULL,'2026-09-18 10:13:32.319788'),(_binary '\êK\ßÀùFsƒ\Î\ÃX&–Û¾','cases','test-cases.xlsx','2026-09-18 08:28:20.943353','2026-09-18 08:28:21.337522',2,2,0,0,'completed',NULL,'2026-09-18 08:28:20.943353'),(_binary '\ì\èK4Bjƒl\İc#\ôÈ·','cases','Cases-18-09-2026.xlsx','2026-09-18 06:30:05.487109','2026-09-18 06:30:30.003442',8948,78,8870,0,'completed',NULL,'2026-09-18 06:30:05.487109'),(_binary '\ì}€L@gƒzI–Š••¯','crm','test-crm.xlsx','2026-09-18 05:20:18.986857','2026-09-18 05:20:19.049288',2,0,2,0,'completed',NULL,'2026-09-18 05:20:18.986857'),(_binary '\ì\è\Ò\Ö/\ÊN\ğ¨^­“\èÀû¬','crm','test-crm.xlsx','2026-09-18 08:28:22.388719','2026-09-18 08:28:22.788600',2,1,1,0,'completed',NULL,'2026-09-18 08:28:22.388719'),(_binary '\íe.\ğD¨G\ë´\\6“^','crm','test-crm.xlsx','2026-09-18 05:20:18.886882','2026-09-18 05:20:18.965899',2,1,1,0,'completed',NULL,'2026-09-18 05:20:18.886882'),(_binary '\ô\ßHc\Ã\ÌGÑ¥Sm²*\Û$','crm','test-crm.xlsx','2026-09-18 10:18:16.416145','2026-09-18 10:18:16.471433',2,1,1,0,'completed',NULL,'2026-09-18 10:18:16.416145'),(_binary '\õrx£•|E¥@Ÿ\Ìå±—„','cases','test-cases.xlsx','2026-09-18 09:55:23.349497','2026-09-18 09:55:23.410984',2,2,0,0,'completed',NULL,'2026-09-18 09:55:23.349497'),(_binary '\õ\îù$D—\ÜB2\Ì\ò','crm','test-crm.xlsx','2026-09-18 10:18:16.475451','2026-09-18 10:18:16.532513',2,0,2,0,'completed',NULL,'2026-09-18 10:18:16.475451'),(_binary 'øø\ßk B¹¬&Š]¡a\Ô','crm','test-crm.xlsx','2026-09-18 07:56:06.545201','2026-09-18 07:56:06.628231',2,0,2,0,'completed',NULL,'2026-09-18 07:56:06.545201'),(_binary 'ùûŸ\å—@LÙ¤\0¥\È{ø\Â','crm','test-crm.xlsx','2026-09-18 10:02:24.207872','2026-09-18 10:02:24.288773',2,1,1,0,'completed',NULL,'2026-09-18 10:02:24.207872'),(_binary 'úCƒQqcLNºF*²m¼¶','crm','test-crm.xlsx','2026-09-18 06:07:27.498919','2026-09-18 06:07:27.582271',2,0,2,0,'completed',NULL,'2026-09-18 06:07:27.498919'),(_binary 'üÙ‹:‹\íL7¦\òz•x','cases','test-cases.xlsx','2026-09-18 08:28:21.370800','2026-09-18 08:28:21.571957',2,0,2,0,'completed',NULL,'2026-09-18 08:28:21.370800'),(_binary 'ı\é\ÈüŒ\òOgŠ­RÆ´‡¾\ñ','crm','test-crm.xlsx','2026-09-18 06:07:27.349088','2026-09-18 06:07:27.465753',2,1,1,0,'completed',NULL,'2026-09-18 06:07:27.349088');
/*!40000 ALTER TABLE `portal_import_history` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portal_submission_attachments`
--

DROP TABLE IF EXISTS `portal_submission_attachments`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_submission_attachments` (
  `attachment_id` binary(16) NOT NULL,
  `submission_id` binary(16) NOT NULL,
  `attachment_kind` varchar(32) NOT NULL,
  `display_order` smallint unsigned NOT NULL,
  `storage_key` varchar(512) NOT NULL,
  `original_filename` varchar(255) NOT NULL,
  `content_type` varchar(127) NOT NULL,
  `byte_size` bigint unsigned NOT NULL,
  `sha256` binary(32) NOT NULL,
  `upload_status` varchar(32) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`attachment_id`),
  UNIQUE KEY `storage_key` (`storage_key`),
  KEY `ix_portal_attachments_submission_kind_order` (`submission_id`,`attachment_kind`,`display_order`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_submission_attachments`
--

LOCK TABLES `portal_submission_attachments` WRITE;
/*!40000 ALTER TABLE `portal_submission_attachments` DISABLE KEYS */;
INSERT INTO `portal_submission_attachments` VALUES (_binary '\0µ€„\ì\íE§	ûvT\ç',_binary '¢]~tm¿Hš“\å!–_D','invoice_image',1,'a25d7e74-6dbf-489a-8193-17e521965f44/invoice_image-01-8b88bc45af174a74b53ba0f5cbe2b804.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-18 10:36:44.777655'),(_binary 'LùW\ÊTKŠ¥œÕŠ\rµ\n+',_binary 'P”\Ê\öK†–Ã²\ãZ]','invoice_image',1,'05509405-caf6-4b17-8696-c3b2e30c5a5d/invoice_image-01-3c03d535b40447ca968acd105b62d10e.jpeg','review_111.jpeg','image/jpeg',98895,_binary 'T\Zûx\ÌıI È\åC†\î-Ù¿›œ¾`——1\Ù]¦','stored','2026-09-17 13:27:59.498035'),(_binary 'B\ÌS6N±€Œ’2¼\ÃJ',_binary 'ü5_>_\ò@\'“\æ\ì\ÊLš','invoice_image',1,'fc355f3e-5ff2-4027-931e-e6ecca4c189a/invoice_image-01-37f92d2a5de94fa9aef8203c14d0c96f.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-19 19:44:59.152524'),(_binary 'p\ÏPiA²Vu¼\Ñ#',_binary '«A:wAÙ€\Ò\÷\Ít¾','product_image',1,'ab41033a-7711-41d9-80d2-f717cd74be02/product_image-01-f01b4dd3d3d843dc92c6e9af867e669d.jpg','image-one.jpg','image/jpeg',9,_binary 'A2AˆB)\É]¤®Àu11¿@5‡EWc\Ög\î\\±)','stored','2026-09-17 12:57:04.673455'),(_binary 'FN—°£¯1¨\õ“',_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','invoice_image',1,'5df1cd3a-d688-4c8e-8f57-f3a46a4a02e3/invoice_image-01-865b88a9fb3d44e7aa6d60bf0d2333bb.png','invoice.png','image/png',12,_binary '_Hşµe\à©b\ÚÇ³RxDG„½<\ét`\ÑXN|%I%.','stored','2026-09-17 12:38:48.183629'),(_binary '1Í¤N\ÚsC	“\ò…ú\â\ã\Ò',_binary '_j¥”\ôCË»\æ\ò\Ä\íRÕ¤','invoice_image',1,'5f7f6aa5-94f4-43cb-bbe6-f2c4ed52d5a4/invoice_image-01-fe09f8a99a324feeb125a1c33276350f.png','invalid.png','image/png',7,_binary '\ñ#Mu‰*:AU¥©\Ïu\Ò\ó>º%\Õu”=M\ö2\ó¤','stored','2026-09-18 10:25:39.876820'),(_binary 'NyŸB-GCèº¦\n~®q\Ù=',_binary 'w3­–¾\×O®¼—švÿzù¶','invoice_image',1,'7733ad96-bed7-4fae-bc97-9a76ff7af9b6/invoice_image-01-499de647c0bf45108bbdc518253ea807.png','invalid.png','image/png',7,_binary '\ñ#Mu‰*:AU¥©\Ïu\Ò\ó>º%\Õu”=M\ö2\ó¤','stored','2026-09-18 10:13:34.028082'),(_binary 'P¸…Ÿ˜IUˆ0Ÿ>ŒT\í\â',_binary '\İü$\ĞXL{±¡\Ú\è‚I~E','invoice_image',1,'ddfc24d0-1b58-4c7b-b1a1-dae882497e45/invoice_image-01-9e352b28cc7f4116b557dd946adf09ad.png','invalid.png','image/png',7,_binary '\ñ#Mu‰*:AU¥©\Ïu\Ò\ó>º%\Õu”=M\ö2\ó¤','stored','2026-09-18 10:18:18.094740'),(_binary 'WĞ®r¸B9“ŒÙ©n¡[\ï',_binary '©‹Hú«GÍ¢ú¼gp','product_image',1,'a90b8b48-faab-47cd-8da2-9d0ffabc6770/product_image-01-345c1f656c524375bb647c596d2c9efa.jpg','image-one.jpg','image/jpeg',9,_binary 'A2AˆB)\É]¤®Àu11¿@5‡EWc\Ög\î\\±)','stored','2026-09-17 12:39:34.150379'),(_binary 'fH\ón0vI<ˆ}\ÎÔ¿¶',_binary '\ä”0ª¿H·	\ëzŠ¤\Í','invoice_image',1,'e4159430-aabf-4805-b709-eb8f7a8aa4cd/invoice_image-01-b435cc5c231b4caa899a01cad8a3a1b8.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-18 10:35:30.569226'),(_binary 'xh\îF^;HØ¬g¾P[»¼\÷',_binary '©‹Hú«GÍ¢ú¼gp','invoice_image',1,'a90b8b48-faab-47cd-8da2-9d0ffabc6770/invoice_image-01-4c309158c8eb46dd9ab8788235c33ab6.png','invoice.png','image/png',12,_binary '_Hşµe\à©b\ÚÇ³RxDG„½<\ét`\ÑXN|%I%.','stored','2026-09-17 12:39:34.150379'),(_binary '|\â\äP-Iu„zÜ·€§Î',_binary '«A:wAÙ€\Ò\÷\Ít¾','product_image',2,'ab41033a-7711-41d9-80d2-f717cd74be02/product_image-02-bdee306ca97f483491b50c364bce14ca.png','image-two.png','image/png',9,_binary 'ü|\ÔKlpv9\à\Ú6–“\æ¬Œ¨\ïC™¬˜U\×','stored','2026-09-17 12:57:04.673455'),(_binary '¡k	µ±gF±ÿj\ÔË¾d',_binary '©‹Hú«GÍ¢ú¼gp','product_image',2,'a90b8b48-faab-47cd-8da2-9d0ffabc6770/product_image-02-4668933b6dea423ca80a0d1c6d5472b3.png','image-two.png','image/png',9,_binary 'ü|\ÔKlpv9\à\Ú6–“\æ¬Œ¨\ïC™¬˜U\×','stored','2026-09-17 12:39:34.150379'),(_binary '¨ƒS\Ø0¨DRƒá\Â0\Z(',_binary 'N’ˆ¨KL\æ›ø\ØøN\ÇS','invoice_image',1,'4e169288-a84b-4ce6-9bf8-d8f84ec7531b/invoice_image-01-41f7bcdb117f4ae4b231dfc43dc124e7.png','invalid.png','image/png',7,_binary '\ñ#Mu‰*:AU¥©\Ïu\Ò\ó>º%\Õu”=M\ö2\ó¤','stored','2026-09-18 10:13:13.115200'),(_binary '¶O\Ó^\ÑK”\Ã\Íš\Ä\\$',_binary '{\ZIMª¬gªe\Í\÷\Ê','invoice_image',1,'191f7b08-1a49-4daa-ac67-aa65cdf71cca/invoice_image-01-a89dd2bb03d247c589305d77f32ba027.png','Screenshot_2026-04-27_132053.png','image/png',92834,_binary 'z›\à|^M\é§+\\ccŸ\ŞKb´.º\'’€\rı­„ø\ñ¤#','stored','2026-09-19 19:45:46.180273'),(_binary '¸B:ÁmuCÎ¸3t¨*g8',_binary '\Z?½\'‹vO\åŸjş[\ğº','invoice_image',1,'1a3fbd27-8b76-4fe5-9f6a-07fe8d5bf0ba/invoice_image-01-4e6575c1a6904f71979017d5d351c04d.png','Screenshot_2026-04-27_143338.png','image/png',43714,_binary 'hšn\Ô\Ù¶\0‚<½\ÔR½Ì»;s\ÎÍ›C¨d9P+»p,','stored','2026-09-18 07:22:58.517614'),(_binary '»\×=\n´EW¡\÷\ğmn ¯',_binary ' ¾\ÇnH1’Q`ç§¬¿','invoice_image',1,'20be03c7-6e1d-4831-927f-5160e7a7acbf/invoice_image-01-cd80db6890b04960a6a3ef27fb18d6c9.png','timing.png','image/png',6,_binary '\öÏ¸\Ã\ñt«?˜·u®báµˆ‘}Gz/LÁ^¹ø','stored','2026-09-18 10:25:17.427449'),(_binary '½\×vj¯HL¯”\ê‚ø\ò',_binary 'ş8ø\Ê9>F-£—r—Š‰ü','invoice_image',1,'fe38f8ca-393e-462d-a397-72978a8904fc/invoice_image-01-03d9e5970cfd447988133d8f46f88969.png','timing.png','image/png',6,_binary '\öÏ¸\Ã\ñt«?˜·u®báµˆ‘}Gz/LÁ^¹ø','stored','2026-09-18 10:25:31.517310'),(_binary '\Ä\Üo\'½¥BE 7ß¸9dN',_binary '¨Q3®ZD\ñ\öE\àBI¡','invoice_image',1,'02a85133-ae5a-44f1-9df6-9045e04249a1/invoice_image-01-4656d288b59a47a296fff358da3a8a6e.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-18 10:32:49.134341'),(_binary '\Ñ5\ä\Î\"¾Je³¢˜x\n2M7',_binary 'ş˜„\î\Ì\"@½«/‘®|¢','invoice_image',1,'fe9884ee-cc22-40bd-ab2f-91ae7ca21e01/invoice_image-01-b848d3499ea44180a56d3d0fb742be1c.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-18 10:35:11.903303'),(_binary '\ÒÿºŞ„@³²u\ï\ñ…|s·',_binary '˜\ÉNş³C—¹\æoşˆ³','invoice_image',1,'0298c94e-feb3-4397-b9e6-6ffe881cb38e/invoice_image-01-5f8029fc8f794598802f4aa9d2c8f5e1.png','invalid.png','image/png',7,_binary '\ñ#Mu‰*:AU¥©\Ïu\Ò\ó>º%\Õu”=M\ö2\ó¤','stored','2026-09-18 10:18:47.007427'),(_binary '\Ó	[\ÆM\rFÙ’\÷\á\Ô&',_binary '³b\ä0¢\nEÎ‹s¸‘l\Æ','invoice_image',1,'b362e430-a20a-45ce-8b73-b8911c126cc6/invoice_image-01-c1d5dfc519d9479ab622aa52bd5fb0f0.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-19 19:38:24.302124'),(_binary '\ÕûociO7 2.·Œ\Ô',_binary 'y\ÍNÿş#AÎ‘\Z^k¬\Ü\r±','invoice_image',1,'79cd4eff-fe23-41ce-911a-5e6bacdc0db1/invoice_image-01-66a49d188808413a8c336622bf9e52cf.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-19 19:44:58.113954'),(_binary '\Ş%x\å(…I0±‘2gw)\÷\n',_binary '«A:wAÙ€\Ò\÷\Ít¾','invoice_image',1,'ab41033a-7711-41d9-80d2-f717cd74be02/invoice_image-01-4c4348a8a85141739553f3e729baa304.png','invoice.png','image/png',12,_binary '_Hşµe\à©b\ÚÇ³RxDG„½<\ét`\ÑXN|%I%.','stored','2026-09-17 12:57:04.673455'),(_binary '\â[²«FE\\‡\ñ§0¯¹&',_binary 'ùÅš\Ç.\Ö@o°\ØIÄ\àº@','invoice_image',1,'f9c59ac7-2ed6-406f-b0d8-49c48de0ba40/invoice_image-01-823e3be306684c06b4a8ba192c3749db.jpg','image_1_.jpg','image/jpeg',171797,_binary '‚!*\ñµ\ò¨D>\Ù\r¿‚\ó\Â\ÍÇ°\âß³&è¿š~½6x¶','stored','2026-09-19 19:32:59.587661'),(_binary '\æE\Ñ`\ÍEA´«JX8YMc',_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','product_image',2,'5df1cd3a-d688-4c8e-8f57-f3a46a4a02e3/product_image-02-582f1bf7e1264247b7add3849ef515ef.png','image-two.png','image/png',9,_binary 'ü|\ÔKlpv9\à\Ú6–“\æ¬Œ¨\ïC™¬˜U\×','stored','2026-09-17 12:38:48.183629'),(_binary '\ëV_\ö>Bç“¦ œR*#',_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','product_image',1,'5df1cd3a-d688-4c8e-8f57-f3a46a4a02e3/product_image-01-e6e21f6ca5944aaba868c3e475e0fb5c.jpg','image-one.jpg','image/jpeg',9,_binary 'A2AˆB)\É]¤®Àu11¿@5‡EWc\Ög\î\\±)','stored','2026-09-17 12:38:48.183629');
/*!40000 ALTER TABLE `portal_submission_attachments` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portal_submission_events`
--

DROP TABLE IF EXISTS `portal_submission_events`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_submission_events` (
  `event_id` bigint unsigned NOT NULL AUTO_INCREMENT,
  `submission_id` binary(16) NOT NULL,
  `case_id` varchar(40) DEFAULT NULL,
  `event_type` varchar(64) NOT NULL,
  `event_payload` json DEFAULT NULL,
  `created_at` datetime(6) NOT NULL,
  PRIMARY KEY (`event_id`),
  KEY `ix_portal_events_submission_created` (`submission_id`,`created_at`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_submission_events`
--

LOCK TABLES `portal_submission_events` WRITE;
/*!40000 ALTER TABLE `portal_submission_events` DISABLE KEYS */;
INSERT INTO `portal_submission_events` VALUES (1,_binary ']\ñ\Í:ÖˆLW\ó¤jJ\ã','DF91-CASE-20260917-C7A9','submission_created','{\"attachment_count\": 3}','2026-09-17 12:38:48.183629'),(2,_binary '©‹Hú«GÍ¢ú¼gp','DF91-CASE-20260917-94FA','submission_created','{\"attachment_count\": 3}','2026-09-17 12:39:34.150379'),(3,_binary '«A:wAÙ€\Ò\÷\Ít¾','DF91-CASE-20260917-05C8','submission_created','{\"attachment_count\": 3}','2026-09-17 12:57:04.673455'),(4,_binary 'P”\Ê\öK†–Ã²\ãZ]','DF91-CASE-20260917-EEAA','submission_created','{\"attachment_count\": 1}','2026-09-17 13:27:59.498035'),(5,_binary '\Z?½\'‹vO\åŸjş[\ğº','DF91-CASE-20260918-D5D3','submission_created','{\"attachment_count\": 1}','2026-09-18 07:22:58.517614'),(6,_binary 'N’ˆ¨KL\æ›ø\ØøN\ÇS','DF91-CASE-20260918-2CDD','submission_created','{\"attachment_count\": 1}','2026-09-18 10:13:13.115200'),(7,_binary 'w3­–¾\×O®¼—švÿzù¶','DF91-CASE-20260918-C4A9','submission_created','{\"attachment_count\": 1}','2026-09-18 10:13:34.028082'),(8,_binary '\İü$\ĞXL{±¡\Ú\è‚I~E','DF91-CASE-20260918-9A36','submission_created','{\"attachment_count\": 1}','2026-09-18 10:18:18.094740'),(9,_binary '˜\ÉNş³C—¹\æoşˆ³','DF91-CASE-20260918-BFF5','submission_created','{\"attachment_count\": 1}','2026-09-18 10:18:47.007427'),(10,_binary ' ¾\ÇnH1’Q`ç§¬¿','DF91-CASE-20260918-93BD','submission_created','{\"attachment_count\": 1}','2026-09-18 10:25:17.427449'),(11,_binary 'ş8ø\Ê9>F-£—r—Š‰ü','DF91-CASE-20260918-49D2','submission_created','{\"attachment_count\": 1}','2026-09-18 10:25:31.517310'),(12,_binary '_j¥”\ôCË»\æ\ò\Ä\íRÕ¤','DF91-CASE-20260918-07B0','submission_created','{\"attachment_count\": 1}','2026-09-18 10:25:39.876820'),(13,_binary '¨Q3®ZD\ñ\öE\àBI¡','DF91-CASE-20260918-B353','submission_created','{\"attachment_count\": 1}','2026-09-18 10:32:49.134341'),(14,_binary 'ş˜„\î\Ì\"@½«/‘®|¢','DF91-CASE-20260918-4FB6','submission_created','{\"attachment_count\": 1}','2026-09-18 10:35:11.903303'),(15,_binary '\ä”0ª¿H·	\ëzŠ¤\Í','DF91-CASE-20260918-46C0','submission_created','{\"attachment_count\": 1}','2026-09-18 10:35:30.569226'),(16,_binary '¢]~tm¿Hš“\å!–_D','DF91-CASE-20260918-3894','submission_created','{\"attachment_count\": 1}','2026-09-18 10:36:44.777655'),(17,_binary 'ùÅš\Ç.\Ö@o°\ØIÄ\àº@','DF91-CASE-20260920-D307','submission_created','{\"attachment_count\": 1}','2026-09-19 19:32:59.587661'),(18,_binary '³b\ä0¢\nEÎ‹s¸‘l\Æ','DF91-CASE-20260920-1948','submission_created','{\"attachment_count\": 1}','2026-09-19 19:38:24.302124'),(19,_binary 'y\ÍNÿş#AÎ‘\Z^k¬\Ü\r±','DF91-CASE-20260920-C92A','submission_created','{\"attachment_count\": 1}','2026-09-19 19:44:58.113954'),(20,_binary 'ü5_>_\ò@\'“\æ\ì\ÊLš','DF91-CASE-20260920-B665','submission_created','{\"attachment_count\": 1}','2026-09-19 19:44:59.152524'),(21,_binary '{\ZIMª¬gªe\Í\÷\Ê','DF91-CASE-20260920-03A1','submission_created','{\"attachment_count\": 1}','2026-09-19 19:45:46.180273');
/*!40000 ALTER TABLE `portal_submission_events` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `portal_submissions`
--

DROP TABLE IF EXISTS `portal_submissions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `portal_submissions` (
  `submission_id` binary(16) NOT NULL,
  `idempotency_key` char(36) NOT NULL,
  `crm_order_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin DEFAULT NULL,
  `crm_product_name` text,
  `crm_purchased_product` text,
  `crm_sku_new` text,
  `crm_customer_name` text,
  `crm_mobile_number` varchar(64) DEFAULT NULL,
  `crm_customer_email` varchar(320) DEFAULT NULL,
  `crm_sales_order_owner` varchar(255) DEFAULT NULL,
  `full_name` varchar(255) NOT NULL,
  `email_address` varchar(320) DEFAULT NULL,
  `phone_number` varchar(32) NOT NULL,
  `alternate_number` varchar(32) DEFAULT NULL,
  `order_id` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_bin NOT NULL,
  `customer_address` text NOT NULL,
  `state` varchar(128) DEFAULT NULL,
  `pincode` varchar(32) NOT NULL,
  `issue_category` varchar(128) NOT NULL,
  `subject` varchar(255) DEFAULT NULL,
  `detailed_description` text NOT NULL,
  `submission_status` varchar(32) NOT NULL,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  PRIMARY KEY (`submission_id`),
  UNIQUE KEY `idempotency_key` (`idempotency_key`),
  KEY `ix_portal_submissions_crm_order_created` (`crm_order_id`,`created_at`),
  KEY `ix_portal_submissions_status_created` (`submission_status`,`created_at`),
  KEY `ix_portal_submissions_order_created` (`order_id`,`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `portal_submissions`
--

LOCK TABLES `portal_submissions` WRITE;
/*!40000 ALTER TABLE `portal_submissions` DISABLE KEYS */;
/*!40000 ALTER TABLE `portal_submissions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Dumping events for database 'durafit_portal'
--

--
-- Dumping routines for database 'durafit_portal'
--
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-09-21 16:11:43
