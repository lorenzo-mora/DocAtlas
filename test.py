from logger.setup import LoggerHandler


try:
    handler = LoggerHandler(
        config_file_path=r"config\logging.ini",
        console_level="INFO",
        file_level="DEBUG",
        log_file_path=r".\logs",
        log_file_name="docatlas",
        max_file_size=524288000,
        backup_count=5,
        console_format='%(asctime)s | %(levelname)s :: %(message)s',
        date_format="%Y-%m-%d %H:%M:%S"
    )
    handler.setup()
except Exception as e:
    print(f"Error while attempting to initialize project logging: {e}")