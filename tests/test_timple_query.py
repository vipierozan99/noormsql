import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from noormsql import Registry, TableBase

registry = Registry()


# This should parse into a pydantic model
class User(TableBase):
    # Still not sure we need this Mapped, SQLModel does not have it
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]


# we want this to be explicit, as to not depend on import order
registry.register(User)


def test_simple_query():
    query = sa.select(User).where(User.id == 1)

    assert (
        query.compile(compile_kwargs={"literal_binds": True})
        == "SELECT user.id, user.name FROM user WHERE user.id = :id_1"
    )
    pass
