-- --------------------------------------------------------
-- Anfitrião:                    127.0.0.1
-- Versão do servidor:           9.6.0 - MySQL Community Server - GPL
-- SO do servidor:               Win64
-- HeidiSQL Versão:              12.5.0.6677
-- --------------------------------------------------------

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET NAMES utf8 */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;


-- A despejar estrutura da base de dados para pap
CREATE DATABASE IF NOT EXISTS `pap` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;
USE `pap`;

-- A despejar estrutura para tabela pap.orders
CREATE TABLE IF NOT EXISTS `orders` (
  `ID` int DEFAULT NULL,
  `Delivery` int DEFAULT NULL,
  `client_ID` int DEFAULT NULL,
  `client_firstName` varchar(255) DEFAULT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- A despejar dados para tabela pap.orders: ~0 rows (aproximadamente)

-- A despejar estrutura para tabela pap.users
CREATE TABLE IF NOT EXISTS `users` (
  `ID` int NOT NULL AUTO_INCREMENT,
  `firstName` varchar(255) NOT NULL,
  `lastName` varchar(255) NOT NULL,
  `email` varchar(255) NOT NULL,
  `password` varchar(255) DEFAULT NULL,
  `recEmail` varchar(255) DEFAULT NULL,
  `gender` varchar(255) DEFAULT NULL,
  `role` enum('client','deliver','restaurant') NOT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `token` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  `tokenTime` varchar(255) CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci DEFAULT NULL,
  PRIMARY KEY (`ID`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB AUTO_INCREMENT=3 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

-- A despejar dados para tabela pap.users: ~2 rows (aproximadamente)
INSERT INTO `users` (`ID`, `firstName`, `lastName`, `email`, `password`, `recEmail`, `gender`, `role`, `created_at`, `update_at`, `token`, `tokenTime`) VALUES
	(1, 'teste', 'test', 'teste', 'teste', 'tes', 'male', 'restaurant', '2026-02-06 15:39:41', '2026-02-06 15:39:43', NULL, NULL),
	(2, 'Testeee', 'Teste', 'a.rochagabri@gmail.com', '$2b$12$eq4qAm3IXbJiXXp32B8TVu6tSDwn2UPx99d36NE0TBiq1gmptXn9i', NULL, NULL, 'client', '2026-02-06 16:41:11', '2026-02-26 21:51:01', NULL, NULL);

/*!40103 SET TIME_ZONE=IFNULL(@OLD_TIME_ZONE, 'system') */;
/*!40101 SET SQL_MODE=IFNULL(@OLD_SQL_MODE, '') */;
/*!40014 SET FOREIGN_KEY_CHECKS=IFNULL(@OLD_FOREIGN_KEY_CHECKS, 1) */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40111 SET SQL_NOTES=IFNULL(@OLD_SQL_NOTES, 1) */;
