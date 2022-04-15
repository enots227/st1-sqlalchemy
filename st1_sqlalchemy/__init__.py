from typing import Iterable
import inspect
from asgiref.sync import sync_to_async
from sqlalchemy import create_engine
from sqlalchemy.engine.url import URL
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from st1_sqlalchemy.types import DBR


class DatabaseContext:

    def __init__(self,
        manager: 'DatabaseManager', 
        use: Iterable[DBR] | DBR=None):
        session_makers: list[sessionmaker] = []

        if not use:
            # default server and database
            session_makers.append(manager.get().get_session_maker())
        else:
            for ref in use:
                host, database = None, None

                if isinstance(ref, tuple):
                    if len(ref) == 2:
                        host, database = ref
                    else:
                        host = ref[0]

                session_makers.append(manager.get(host).get_session_maker(
                    database))

        self.session_makers = tuple(session_makers)
        self.sessions: tuple[Session | AsyncSession]|None = None

    async def __aenter__(self) -> tuple[Session | AsyncSession] | Session | \
        AsyncSession:
        self.sessions = tuple(session_maker() for session_maker in 
            self.session_makers)

        if len(self.sessions) == 1:
            print('RETURN SESSION')
            return self.sessions[0]

        return self.sessions

    async def __aexit__(self, type, value, traceback):
        if not self.sessions:
            return

        for session in self.sessions:
            if inspect.iscoroutinefunction(session):
                await session.close()
            else:
                print('CLOSING SYNC SESSION')
                await sync_to_async(session.close)()


class DatabaseServer:
    
    def __init__(self,
        host: str,
        username: str,
        password: str,
        port: int = 1433,
        engine: str = 'mssql',
        default: str | None=None):
        """Initialize the database manager.

        Args:
            host: The database server host name.
            username: The database username.
            password: The database password.
            port: The database server port number. Defaults to the standard 
                MSSQL database port (1433).
            engine: The type of database server engine. Defaults to MSSQL.
            default_db: The default database name.
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        
        self._create_engine = getattr(self, f'_create_{engine}')

        self.__databases = {}
        self.default_database = default

        if default:
            self._get_or_create(default)

    def _create_mssql(self, database: str) -> Engine:
        """Create a Microsoft SQL (MSSQL) SQLAlchemy Engine.

        Args:
            database: The database name.

        Returns:
            The SQLAlchemy Engine for MSSQL.
        """
        connection_url = URL.create(
            cls="mssql+pyodbc",
            drivername="ODBC Driver 17 for SQL Server",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database)

        return create_engine(connection_url, encoding='latin1', echo=True)

    def _create_postgres(self, database: str) -> Engine:
        """Create a Postgres SQLAlchemy Engine.

        Args:
            database: The database name.

        Returns:
            The SQLAlchemy Engine for Postgres.
        """
        connection_url = URL.create(
            "postgresql",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database)
            
        return create_engine(connection_url, encoding='latin1', echo=True)

    def _create_async_postgres(self, database: str) -> AsyncEngine:
        """Create a Postgres SQLAlchemy Engine.

        Args:
            database: The database name.

        Returns:
            The SQLAlchemy Engine for Postgres.
        """
        connection_url = URL.create(
            "postgresql+asyncpg",
            username=self.username,
            password=self.password,
            host=self.host,
            port=self.port,
            database=database)
            
        return create_async_engine(connection_url, echo=True)

    def _create(self, database: str) -> tuple[Engine | AsyncEngine, \
        sessionmaker]:
        """Get existing or create a database engine instance.

        Args:
            database: The database name.

        Returns:
            * The database engine.
            * The session maker.
        """
        engine = self._create_engine(database)

        session_cls = AsyncEngine if isinstance(engine, AsyncEngine) else \
            Session
        session_maker = sessionmaker(engine, session_cls, 
            expire_on_commit=False)

        self.__databases[database] = (engine, session_maker)

        return engine, session_maker

    def _get_or_create(self, database: str) -> tuple[Engine | AsyncEngine, \
        sessionmaker]:
        """Get existing or create a database engine instance.

        Args:
            database: The database name.

        Returns:
            * The database engine.
            * The session maker.
        """
        if database not in self.__databases:
            return self._create(database)

        return self.__databases[database]

    def get_session_maker(self, database: str | None=None) -> sessionmaker:
        """Get a session for the databse.

        Args:
            database: The databse name.
        
        Returns:
            A database session.
        """
        if not database:
            database = self.default_database

        _, session_maker = self._get_or_create(database)

        return session_maker


class DatabaseManager:

    def __init__(self, *db_servers: DatabaseServer):
        self.__database_servers: dict[str, DatabaseServer] = {}

        if len(db_servers) > 0:
            self.default_server = db_servers[0].host

        self.add(*db_servers)

    def add(self, *db_servers: DatabaseServer) -> None:
        """Create the database server connection manager.

        Args:
            db_servers: One or more database server manager.
        """
        for db_server in db_servers:
            self.__database_servers[db_server.host] = db_server

    def get(self, host: str | None=None) -> DatabaseServer:
        if not host:
            return self.__database_servers[self.default_server]

        return self.__database_servers[host]

    def db_context(self, use: list[DBR] | DBR=None) \
        -> DatabaseContext:
        return DatabaseContext(self, use)

