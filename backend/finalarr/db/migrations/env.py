from alembic import context

from finalarr.db.models import Base

engine = context.config.attributes["engine"]

with engine.connect() as connection:
    # Batch migrations rebuild a table (copy, drop the old one, rename). With foreign keys
    # on, dropping the old table cascades into its children: 0004 emptied deliveries and
    # 0010 seasons and episodes. SQLite ignores this pragma inside a transaction, so it is
    # set before one starts, and the references are checked once all migrations ran.
    connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
    try:
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()
            broken = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
            if broken:
                raise RuntimeError(f"Migration left broken references: {broken[:5]}")
        connection.commit()
    finally:
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")
