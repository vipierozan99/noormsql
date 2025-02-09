import sqlalchemy as sa
import sqlfluff

from noormsql import TableBase, TableRegistry

registry = TableRegistry()


metadata = sa.MetaData()

user_table = sa.Table(
    "user",
    metadata,
    sa.Column("name", sa.String),
)


# This should parse into a pydantic model
class User(TableBase):
    __table__ = user_table
    # Still not sure we need this Mapped, SQLModel does not have it
    name: str


# we want this to be explicit, as to not depend on import order
registry.register(User)


def test_simple_query():
    query = sa.select(User.name).where(User.name == "Victor")

    assert_sql(
        str(query.compile(compile_kwargs={"literal_binds": True})),
        """
        SELECT "user".name FROM "user" WHERE "user".name = 'Victor'
        """,
    )


def canon_sql(sql: str):
    return sqlfluff.fix(sql.replace("\n", ""))


def assert_sql(sql: str, expected: str):
    assert canon_sql(sql) == canon_sql(expected)
