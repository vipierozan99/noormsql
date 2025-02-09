import typing
from typing import Any, ClassVar, Optional, Self, Type

from sqlalchemy import FromClause, MetaData
from sqlalchemy.orm import InstanceState, Mapper


class TableBase:
    metadata: ClassVar[MetaData]
    __table__: Optional[FromClause]

    if typing.TYPE_CHECKING:

        def _sa_inspect_type(self) -> Mapper[Self]: ...

        def _sa_inspect_instance(self) -> InstanceState[Self]: ...

        __tablename__: Any
        """String name to assign to the generated
        :class:`_schema.Table` object, if not specified directly via
        :attr:`_orm.DeclarativeBase.__table__`.

        .. seealso::

            :ref:`orm_declarative_table`

        """

        __mapper_args__: Any
        """Dictionary of arguments which will be passed to the
        :class:`_orm.Mapper` constructor.

        .. seealso::

            :ref:`orm_declarative_mapper_options`

        """

        __table_args__: Any
        """A dictionary or tuple of arguments that will be passed to the
        :class:`_schema.Table` constructor.  See
        :ref:`orm_declarative_table_configuration`
        for background on the specific structure of this collection.

        .. seealso::

            :ref:`orm_declarative_table_configuration`

        """

        def __init__(self, **kw: Any): ...

    pass


class Registry:
    def register(self, cls: Type[TableBase]) -> None:
        pass
