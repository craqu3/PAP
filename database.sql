create table users (
id INT auto_increment primary key,
role ENUM('customer','restaurant','deliver') NOT NULL,
name VARCHAR(20),
surname VARCHAR(20),
email VARCHAR(150) UNIQUE NOT NULL,
recEmail VARCHAR(150) UNIQUE NOT NULL,
password VARCHAR(255) NOT NULL,
created_at DATETIME DEFAULT current_timestamp,
last_update DATETIME DEFAULT current_timestamp on update current_timestamp
);

create table avaliations (
user_id INT UNIQUE NOT NULL primary key,
name VARCHAR(20),
surname VARCHAR(20),
email varchar(150),
created_at DATETIME DEFAULT current_timestamp,
last_update DATETIME DEFAULT current_timestamp on update current_timestamp
);

create table delivery (
ID  INT auto_increment UNIQUE NOT NULL primary key,
rating INT,
damage INT,
temperature INT,
deliverStatus ENUM('Done','In progress','Cancelled') NOT NULL,
clientOrder varchar(255),
created_at DATETIME DEFAULT current_timestamp,
last_update DATETIME DEFAULT current_timestamp on update current_timestamp
)
