import typing
from typing import (
    Any,
    Callable,
    ClassVar,
    Dict,
    Literal,
    Mapping,
    Optional,
    Self,
    Set,
    Tuple,
    Type,
    TypeAlias,
    TypeVar,
    Union,
    cast,
)

import sqlalchemy as sa
from pydantic import BaseConfig, BaseModel
from pydantic._internal._model_construction import ModelMetaclass
from pydantic_core import PydanticUndefined as Undefined
from pydantic_core import PydanticUndefinedType as UndefinedType
from sqlalchemy import FromClause, MetaData
from sqlalchemy.orm import InstanceState, Mapper

from noormsql._compat import (
    PYDANTIC_VERSION,
    SQLModelConfig,
    finish_init,
    get_config_value,
    get_model_fields,
    set_config_value,
    sqlmodel_init,
    sqlmodel_validate,
)

_T = TypeVar("_T")
NoArgAnyCallable = Callable[[], Any]
IncEx: TypeAlias = Union[
    Set[int],
    Set[str],
    Mapping[int, Union["IncEx", Literal[True]]],
    Mapping[str, Union["IncEx", Literal[True]]],
]
OnDeleteType = Literal["CASCADE", "SET NULL", "RESTRICT"]


def get_column_from_field(field: Any) -> sa.Column:  # type: ignore
    ...


class TableRegistry:
    def register(self, cls: Type["TableBase"]) -> None:
        pass


class TableBaseMetaclass(ModelMetaclass):
    registry: ClassVar[TableRegistry]
    metadata: ClassVar[MetaData]
    __table__: Optional[FromClause]

    if typing.TYPE_CHECKING:

        def _sa_inspect_type(self) -> Mapper[Self]: ...
        def _sa_inspect_instance(self) -> InstanceState[Self]: ...

        __tablename__: Any

    # From Pydantic
    def __new__(
        cls,
        name: str,
        bases: Tuple[Type[Any], ...],
        class_dict: Dict[str, Any],
        **kwargs: Any,
    ) -> Any:
        dict_for_pydantic = {}
        original_annotations = class_dict.get("__annotations__", {})
        pydantic_annotations = {}
        for k, v in class_dict.items():
            dict_for_pydantic[k] = v
        for k, v in original_annotations.items():
            pydantic_annotations[k] = v
        dict_used = {
            **dict_for_pydantic,
            "__weakref__": None,
            "__annotations__": pydantic_annotations,
        }
        # Duplicate logic from Pydantic to filter config kwargs because if they are
        # passed directly including the registry Pydantic will pass them over to the
        # superclass causing an error
        allowed_config_kwargs: Set[str] = {
            key
            for key in dir(BaseConfig)
            if not (
                key.startswith("__") and key.endswith("__")
            )  # skip dunder methods and attributes
        }
        config_kwargs = {
            key: kwargs[key] for key in kwargs.keys() & allowed_config_kwargs
        }
        new_cls = super().__new__(cls, name, bases, dict_used, **config_kwargs)
        new_cls.__annotations__ = {
            **pydantic_annotations,
            **new_cls.__annotations__,
        }

        def get_config(name: str) -> Any:
            config_class_value = get_config_value(
                model=new_cls, parameter=name, default=Undefined
            )
            if config_class_value is not Undefined:
                return config_class_value
            kwarg_value = kwargs.get(name, Undefined)
            if kwarg_value is not Undefined:
                return kwarg_value
            return Undefined

        config_table = get_config("table")
        if config_table is True:
            # If it was passed by kwargs, ensure it's also set in config
            set_config_value(model=new_cls, parameter="table", value=config_table)
            for k, v in get_model_fields(new_cls).items():
                col = get_column_from_field(v)
                setattr(new_cls, k, col)
            # Set a config flag to tell FastAPI that this should be read with a field
            # in orm_mode instead of preemptively converting it to a dict.
            # This could be done by reading new_cls.model_config['table'] in FastAPI, but
            # that's very specific about SQLModel, so let's have another config that
            # other future tools based on Pydantic can use.
            set_config_value(
                model=new_cls, parameter="read_from_attributes", value=True
            )
            # For compatibility with older versions
            # TODO: remove this in the future
            set_config_value(model=new_cls, parameter="read_with_orm_mode", value=True)

        return new_cls


_TTableBase = TypeVar("_TTableBase", bound="TableBase")


class TableBase(BaseModel, metaclass=TableBaseMetaclass):
    # SQLAlchemy needs to set weakref(s), Pydantic will set the other slots values
    __slots__ = ("__weakref__",)
    __tablename__: ClassVar[Union[str, Callable[..., str]]]
    __name__: ClassVar[str]
    metadata: ClassVar[MetaData]
    __allow_unmapped__ = True  # https://docs.sqlalchemy.org/en/20/changelog/migration_20.html#migration-20-step-six

    model_config = SQLModelConfig(from_attributes=True)

    def __new__(cls, *args: Any, **kwargs: Any) -> Any:
        new_object = super().__new__(cls)
        # SQLAlchemy doesn't call __init__ on the base class when querying from DB
        # Ref: https://docs.sqlalchemy.org/en/14/orm/constructors.html
        # Set __fields_set__ here, that would have been set when calling __init__
        # in the Pydantic model so that when SQLAlchemy sets attributes that are
        # added (e.g. when querying from DB) to the __fields_set__, this already exists
        # init_pydantic_private_attrs(new_object)
        return new_object

    def __init__(__pydantic_self__, **data: Any) -> None:
        # Uses something other than `self` the first arg to allow "self" as a
        # settable attribute

        # SQLAlchemy does very dark black magic and modifies the __init__ method in
        # sqlalchemy.orm.instrumentation._generate_init()
        # so, to make SQLAlchemy work, it's needed to explicitly call __init__ to
        # trigger all the SQLAlchemy logic, it doesn't work using cls.__new__, setting
        # attributes obj.__dict__, etc. The __init__ method has to be called. But
        # there are cases where calling all the default logic is not ideal, e.g.
        # when calling Model.model_validate(), as the validation is done outside
        # of instance creation.
        # At the same time, __init__ is what users would normally call, by creating
        # a new instance, which should have validation and all the default logic.
        # So, to be able to set up the internal SQLAlchemy logic alone without
        # executing the rest, and support things like Model.model_validate(), we
        # use a contextvar to know if we should execute everything.
        if finish_init.get():
            sqlmodel_init(self=__pydantic_self__, data=data)

    @classmethod
    def model_validate(
        cls: Type[_TTableBase],
        obj: Any,
        *,
        strict: Union[bool, None] = None,
        from_attributes: Union[bool, None] = None,
        context: Union[Dict[str, Any], None] = None,
        update: Union[Dict[str, Any], None] = None,
    ) -> _TTableBase:
        return sqlmodel_validate(
            cls=cls,
            obj=obj,
            strict=strict,
            from_attributes=from_attributes,
            context=context,
            update=update,
        )

    def model_dump(
        self,
        *,
        mode: Union[Literal["json", "python"], str] = "python",
        include: Union[IncEx, None] = None,
        exclude: Union[IncEx, None] = None,
        context: Union[Dict[str, Any], None] = None,
        by_alias: bool = False,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        round_trip: bool = False,
        warnings: Union[bool, Literal["none", "warn", "error"]] = True,
        serialize_as_any: bool = False,
    ) -> Dict[str, Any]:
        if PYDANTIC_VERSION >= "2.7.0":
            extra_kwargs: Dict[str, Any] = {
                "context": context,
                "serialize_as_any": serialize_as_any,
            }
        else:
            extra_kwargs = {}
        return super().model_dump(
            mode=mode,
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
            round_trip=round_trip,
            warnings=warnings,
            **extra_kwargs,
        )

    def sqlmodel_update(
        self: _TTableBase,
        obj: Union[Dict[str, Any], BaseModel],
        *,
        update: Union[Dict[str, Any], None] = None,
    ) -> _TTableBase:
        use_update = (update or {}).copy()
        if isinstance(obj, dict):
            for key, value in {**obj, **use_update}.items():
                if key in get_model_fields(self):
                    setattr(self, key, value)
        elif isinstance(obj, BaseModel):
            for key in get_model_fields(obj):
                if key in use_update:
                    value = use_update.pop(key)
                else:
                    value = getattr(obj, key)
                setattr(self, key, value)
            for remaining_key in use_update:
                if remaining_key in get_model_fields(self):
                    value = use_update.pop(remaining_key)
                    setattr(self, remaining_key, value)
        else:
            raise ValueError(
                "Can't use sqlmodel_update() with something that "
                f"is not a dict or SQLModel or Pydantic model: {obj}"
            )
        return self
