import io
import logging

import pytest

from jupyter_events.logger import EventLogger, ListenerError
from jupyter_events.schema import EventSchema

from .utils import SCHEMA_PATH


@pytest.fixture
def schema():
    # Read schema from path.
    schema_path = SCHEMA_PATH / "good" / "basic.yaml"
    return EventSchema(schema=schema_path)


@pytest.fixture
def event_logger(schema):
    logger = EventLogger()
    logger.register_event_schema(schema)
    return logger


async def test_listener_function(event_logger, schema):
    global listener_was_called
    listener_was_called = False

    async def my_listener(logger: EventLogger, schema_id: str, data: dict) -> None:
        global listener_was_called
        listener_was_called = True  # type: ignore

    # Add the modifier
    event_logger.add_listener(schema_id=schema.id, listener=my_listener)
    event_logger.emit(schema_id=schema.id, data={"prop": "hello, world"})
    await event_logger.gather_listeners()
    assert listener_was_called
    # Check that the active listeners are cleaned up.
    assert len(event_logger._active_listeners) == 0


async def test_bad_listener_function_signature(event_logger, schema):
    async def listener_with_extra_args(
        logger: EventLogger, schema_id: str, data: dict, unknown_arg: dict
    ) -> None:
        pass

    with pytest.raises(ListenerError):
        event_logger.add_listener(
            schema_id=schema.id,
            listener=listener_with_extra_args,
        )

    # Ensure no modifier was added.
    assert len(event_logger._unmodified_listeners[schema.id]) == 0


async def test_listener_that_raises_exception(event_logger, schema):
    # Get an application logger that will show the exception
    app_log = event_logger.log
    log_stream = io.StringIO()
    h = logging.StreamHandler(log_stream)
    app_log.addHandler(h)

    async def listener_raise_exception(
        logger: EventLogger, schema_id: str, data: dict
    ) -> None:
        raise Exception("This failed")

    event_logger.add_listener(schema_id=schema.id, listener=listener_raise_exception)
    event_logger.emit(schema_id=schema.id, data={"prop": "hello, world"})

    await event_logger.gather_listeners()

    # Check that the exception was printed to the logs
    h.flush()
    log_output = log_stream.getvalue()
    assert "This failed" in log_output
    # Check that the active listeners are cleaned up.
    assert len(event_logger._active_listeners) == 0


async def test_bad_listener_does_not_break_good_listener(event_logger, schema):
    # Get an application logger that will show the exception
    app_log = event_logger.log
    log_stream = io.StringIO()
    h = logging.StreamHandler(log_stream)
    app_log.addHandler(h)

    global listener_was_called
    listener_was_called = False

    async def listener_raise_exception(
        logger: EventLogger, schema_id: str, data: dict
    ) -> None:
        raise Exception("This failed")

    async def my_listener(logger: EventLogger, schema_id: str, data: dict) -> None:
        global listener_was_called
        listener_was_called = True  # type: ignore

    # Add a bad listener and a good listener and ensure that
    # emitting still works and the bad listener's exception is is logged.
    event_logger.add_listener(schema_id=schema.id, listener=listener_raise_exception)
    event_logger.add_listener(schema_id=schema.id, listener=my_listener)

    event_logger.emit(schema_id=schema.id, data={"prop": "hello, world"})

    await event_logger.gather_listeners()

    # Check that the exception was printed to the logs
    h.flush()
    log_output = log_stream.getvalue()
    assert "This failed" in log_output
    assert listener_was_called
    # Check that the active listeners are cleaned up.
    assert len(event_logger._active_listeners) == 0
