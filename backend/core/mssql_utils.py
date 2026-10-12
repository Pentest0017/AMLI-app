"""Helpers for hand-written SQL Server (mssql-django) migration steps.

SQL Server refuses ``ALTER TABLE ... DROP COLUMN`` while anything still depends on the
column (foreign keys, check/default/unique constraints, indexes). PostgreSQL and SQLite
do not have this limitation, so these helpers are only used from the ``microsoft``/``mssql``
branches of migrations.
"""

MSSQL_VENDORS = ("microsoft", "mssql")


def is_mssql(schema_editor):
    return schema_editor.connection.vendor in MSSQL_VENDORS


def drop_column(cursor, table, column):
    """Drop ``table.column`` (if present) together with every object that depends on it."""
    cursor.execute(
        f"""
        IF EXISTS (SELECT * FROM sys.columns WHERE object_id = OBJECT_ID('{table}') AND name = '{column}')
        BEGIN
            DECLARE @sql NVARCHAR(MAX) = N'';
            DECLARE @col_id INT = COLUMNPROPERTY(OBJECT_ID('{table}'), '{column}', 'ColumnId');

            -- foreign keys that use the column
            SELECT @sql += N'ALTER TABLE {table} DROP CONSTRAINT ' + QUOTENAME(fk.name) + N';'
            FROM sys.foreign_keys fk
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            WHERE fkc.parent_object_id = OBJECT_ID('{table}') AND fkc.parent_column_id = @col_id;

            -- check constraints on the column
            SELECT @sql += N'ALTER TABLE {table} DROP CONSTRAINT ' + QUOTENAME(cc.name) + N';'
            FROM sys.check_constraints cc
            WHERE cc.parent_object_id = OBJECT_ID('{table}') AND cc.parent_column_id = @col_id;

            -- default constraints on the column
            SELECT @sql += N'ALTER TABLE {table} DROP CONSTRAINT ' + QUOTENAME(dc.name) + N';'
            FROM sys.default_constraints dc
            WHERE dc.parent_object_id = OBJECT_ID('{table}') AND dc.parent_column_id = @col_id;

            -- unique constraints that include the column
            SELECT @sql += N'ALTER TABLE {table} DROP CONSTRAINT ' + QUOTENAME(i.name) + N';'
            FROM sys.indexes i
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            WHERE i.object_id = OBJECT_ID('{table}') AND ic.column_id = @col_id
              AND i.is_unique_constraint = 1;

            -- plain / unique indexes that include the column (not PK, not constraints)
            SELECT @sql += N'DROP INDEX ' + QUOTENAME(i.name) + N' ON {table};'
            FROM sys.indexes i
            JOIN sys.index_columns ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
            WHERE i.object_id = OBJECT_ID('{table}') AND ic.column_id = @col_id
              AND i.is_primary_key = 0 AND i.is_unique_constraint = 0 AND i.type > 0;

            SET @sql += N'ALTER TABLE {table} DROP COLUMN ' + QUOTENAME('{column}') + N';';
            EXEC sp_executesql @sql;
        END;
        """
    )
