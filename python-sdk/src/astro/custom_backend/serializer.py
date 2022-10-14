from __future__ import annotations

import json
import logging
from json import JSONDecodeError
from typing import Any

import numpy as np
import pandas

from astro.files import File
from astro.table import Table, TempTable

log = logging.getLogger("astro.utils.serializer")


def serialize(obj: Table | File | Any) -> dict | Any:  # noqa
    """
    Serialize astro SDK objects (tables, files and dataframes) into json safe dictionary

    :param obj: object to serialize
    :return:
    """
    if isinstance(obj, (Table, TempTable)):
        return obj.to_json()
    elif isinstance(obj, File):
        return obj.to_json()
    elif isinstance(obj, (list, tuple)):
        return [serialize(o) for o in obj]
    elif isinstance(obj, dict):
        return {k: serialize(v) for k, v in obj.items()}
    elif isinstance(obj, pandas.DataFrame):
        from astro.utils.dataframe import convert_dataframe_to_file

        file = convert_dataframe_to_file(obj)
        return serialize(file)
    elif isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return np.float64(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, str):
        return {"class": "string", "value": obj}
    else:
        return _attempt_to_serialize_unknown_object(obj)


def _attempt_to_serialize_unknown_object(obj: object):
    try:
        return json.dumps(obj)
    except TypeError:
        return obj


def _is_serialized_astro_object(obj) -> bool:
    return bool(obj.get("class") and obj["class"] in ["Table", "File", "string"])


def deserialize(obj: dict | str | list) -> Table | File | Any:
    """
    Deserialize json dictionaries into astro SDK objects (tables, files, dataframes, etc.)

    :param obj: serialized object to deserialize
    :return:
    """
    if isinstance(obj, (list, tuple)):
        return [deserialize(o) for o in obj]
    if isinstance(obj, dict) and _is_serialized_astro_object(obj):
        if obj["class"] == "Table":
            log.debug("Found table dictionary %s, will attempt to deserialize", obj)
            return Table.from_json(obj)
        elif obj["class"] == "File":
            log.debug("Found file dictionary %s, will attempt to deserialize", obj)
            return _deserialize_file(obj)
        else:
            return obj["value"]
    elif isinstance(obj, dict):
        return {k: deserialize(v) for k, v in obj.items()}
    elif isinstance(obj, str):
        log.debug("Found string, will attempt to deserialize")
        return _attempt_to_deser_unknown_object(obj)
    else:
        return obj


def _deserialize_file(obj):
    file = File.from_json(obj)
    if file.is_dataframe:
        return file.export_to_dataframe()
    return file


def _attempt_to_deser_unknown_object(obj: str):
    try:
        log.debug("Attempting to deserialize object %s into a json object", obj)
        return json.loads(obj)
    except JSONDecodeError:
        log.debug("Json deserializing failed for object %s, returning raw object", obj)
        return obj
