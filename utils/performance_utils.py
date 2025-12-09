# ============================================================================
# SECCIÓN 1: IMPORTS
# ============================================================================

# Librerías estándar
import logging as log
import functools
import inspect
import os
import re
from time import time
from typing import Callable

# Librerías de terceros
from typeguard import typechecked
import pandas as pd
import polars as pl
from utils.logging_utils import (
    get_time_for_loggers,
    setup_logger_for_child,
)


_POLARS_TYPE_MAP = {
    'str': pl.Utf8,
    'int': pl.Int64,
    'float': pl.Float64,
    'date': pl.Date,
    'datetime': pl.Datetime
}

def cast_columns(df: pl.DataFrame, schema: dict) -> pl.DataFrame:
    """
    Convierte las columnas de un DataFrame a los tipos especificados en el
    schema.

    Parameters
    ----------
    df : pl.DataFrame
        DataFrame cuyas columnas se van a convertir.
    schema : dict
        Diccionario donde las claves son nombres de columnas y los valores
        son tuplas (tipo_esperado, formato_opcional).

    Returns
    -------
    pl.DataFrame
        DataFrame con columnas convertidas a sus tipos respectivos.

    Raises
    ------
    ValueError
        Si alguna columna requerida del schema no existe en el DataFrame.
    """
    # Encontrar columnas faltantes
    missing_columns = [col_name for col_name in schema
                       if col_name not in df.columns]

    if missing_columns:
        raise ValueError(f"Missing required columns: {missing_columns}")

    transformations = []

    for col_name, (expected_type, fmt) in schema.items():
        current_dtype = df[col_name].dtype
        target_dtype = _POLARS_TYPE_MAP.get(expected_type)
        if target_dtype is None:
            raise ValueError(f"Unsupported type '{expected_type}' in schema")

        if current_dtype != target_dtype:
            if expected_type in ['date', 'datetime'] and fmt:
                transformations.append(
                    pl.col(col_name)
                    .str.strptime(target_dtype, fmt)
                    .alias(col_name)
                )
            else:
                transformations.append(
                    pl.col(col_name)
                    .cast(target_dtype)
                    .alias(col_name)
                )

    if len(transformations) > 0:
        # Aplicando transformaciones
        df = df.with_columns(transformations)

    return df


def parse_schema(docstring: str) -> dict[str, dict]:
    """
    Parsea el schema y meta instrucciones del docstring de una función
    usando expresiones regulares.

    Pasos
    -----
    1. Extrae nombres de DataFrame usando regex.
    2. Para cada DataFrame, aísla el bloque de schema entre la declaración
       del DataFrame y 'Returns'.
    3. Usa regex para capturar nombres de columnas, tipos y formatos opcionales.
    4. Guarda el schema en un diccionario bajo el nombre del DataFrame.
    5. Busca y guarda cualquier 'Meta instruction' encontrada.
    6. Retorna un diccionario mapeando nombres de DataFrame a sus schemas
       y meta instrucciones.

    Parameters
    ----------
    docstring : str
        Docstring de la función que puede tener una definición de schema.

    Returns
    -------
    Dict[str, dict]
        Diccionario donde las claves son nombres de frames y los valores
        son diccionarios conteniendo el schema y meta instrucciones.
    """
    schema_dict = {}

    # Definir patrones regex para encontrar información de interés
    pattern_df = r"(\w+)\s*:\s*pl\.DataFrame"
    pattern_schema = r"\|\--\s*(\w+)\s*:\s*(\w+)(?:\s*\(format:\s*(.*?)\))?"
    pattern_meta = r"Meta instruction:\s*(.*)"

    # Encontrar todos los nombres de DataFrame
    df_matches = re.findall(pattern_df, docstring)

    multiple_matches = len(df_matches) > 1

    key = 'Drop extra columns.'
    for df_name in df_matches:
        # Extraer el bloque de schema para cada DataFrame
        schema_start = docstring.find(f"{df_name}: pl.DataFrame")
        schema_text = docstring.split("Returns")[0][schema_start:]
        if multiple_matches and key in schema_text:
            schema_end = schema_text.find(key) + len(key)
            if schema_end > 0:
                schema_text = schema_text[:schema_end]

        schema_dict[df_name] = {'schema': {}, 'meta_instructions': []}

        # Usar regex para extraer nombres de columnas, tipos y formatos
        for match in re.finditer(pattern_schema, schema_text):
            col_name, col_type, col_format = match.groups()
            schema_dict[df_name]['schema'][col_name] = \
                (col_type, col_format or None)

        # Extraer meta instrucciones
        meta_match = re.search(pattern_meta, schema_text)
        if meta_match:
            schema_dict[df_name]['meta_instructions'] \
                .append(meta_match.group(1))

    return schema_dict


def timeit_(func: Callable, log):
    """
    Calcula el tiempo de ejecución de un método usando el logger proporcionado.

    Parameters
    ----------
    func : Callable
        Función a decorar.
    log : logging.Logger
        Logger para registrar información de timing.

    Returns
    -------
    Callable
        Función decorada con funcionalidad de timing.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        tic = time()
        log.info('Initiating process.')
        result = func(*args, **kwargs)
        toc = time()

        time_message = get_time_for_loggers(tic=tic, toc=toc)
        log.info(f'Done. {time_message}.')

        return result

    return wrapper


def validate_schema(func: Callable, log) -> Callable:
    """
    Decorador que valida y convierte columnas de DataFrames basándose en
    el schema definido en el docstring, y registra cualquier columna extra
    presente.

    Si "Meta instruction: Drop extra columns" está presente para un DataFrame
    específico, las columnas extra serán eliminadas.

    Parameters
    ----------
    func : Callable
        Función que procesa el/los DataFrame(s).
    log : Logger
        Logger para registrar columnas extra y problemas de schema.

    Returns
    -------
    Callable
        Función envuelta con validación de schema y logging.

    Raises
    ------
    TypeError
        Si el argumento DataFrame esperado no se pasa o no coincide con
        el schema.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Extraer el docstring
        docstring = inspect.getdoc(func)

        if docstring is None:
            return func(*args, **kwargs)

        # Si no se encuentra schema, no hacer nada
        if 'Schema:' not in docstring:
            return func(*args, **kwargs)

        # Parsear schema y asociar DataFrames
        schemas = parse_schema(docstring)

        # Iterar sobre los argumentos para validar DataFrames por nombre
        for df_name, schema_info in schemas.items():
            schema = schema_info['schema']
            meta_instructions = schema_info['meta_instructions']
            if len(meta_instructions) != 0:
                drop_extra = 'Drop extra columns' in meta_instructions[0]
            else:
                drop_extra = False

            sig = inspect.signature(func)
            bound_args = sig.bind_partial(*args, **kwargs).arguments
            df = bound_args.get(df_name)

            if df is None:
                raise TypeError(f"Expected DataFrame '{df_name}' not passed.")

            schema_columns = set(schema.keys())
            df_columns = set(df.columns)

            extra_columns = df_columns - schema_columns
            if extra_columns and log:
                log.info(f"Extra columns found in DataFrame '{df_name}': "
                         f"{extra_columns}")

            # Validar y convertir columnas
            df = cast_columns(df, schema)

            # Encontrar columnas extra
            schema_columns = set(schema.keys())
            df_columns = set(df.columns)
            extra_columns = df_columns - schema_columns

            # Eliminar columnas extra si la meta instrucción está presente
            if extra_columns and drop_extra:
                if log:
                    log.warning(f"Dropping extra columns from DataFrame "
                                f"'{df_name}': {extra_columns}")
                df = df.drop(list(extra_columns))

            # Actualizar el DataFrame en kwargs
            kwargs[df_name] = df

        # Llamar a la función original con los DataFrames validados
        return func(*args, **kwargs)

    return wrapper


# ============================================================================
# SECCIÓN 6: FUNCIÓN DE PROCESAMIENTO
# ============================================================================

def process_method(attr_name: str,
                   attr_value,
                   conditions: dict,
                   new_attributes: dict,
                   name: str,
                   log_level: str,
                   log_file: str) -> dict:

    log = setup_logger_for_child(
        parent_name=name,
        child_name=attr_name,
        log_file=log_file,
        log_level=log_level,
    )

    if conditions['call_condition']:
        log_attr_name = f'log_{attr_name}'
        new_attributes[log_attr_name] = log

    if conditions['all_conditions']:
        attr_value = typechecked(attr_value)
        attr_value = timeit_(func=attr_value, log=log)
        attr_value = validate_schema(func=attr_value, log=log)

    if conditions['is_static']:
        new_attributes[attr_name] = staticmethod(attr_value)
    elif conditions['is_classm']:
        new_attributes[attr_name] = classmethod(attr_value)
    else:
        new_attributes[attr_name] = attr_value

    return new_attributes


# ============================================================================
# SECCIÓN 7: METACLASE
# ============================================================================

class MetaEngine(type):
    """
    Metaclase que agrega funcionalidades automáticas de logging, timing y
    verificación de type hints a las clases.

    Esta metaclase realiza lo siguiente:
    1. Para cada método en la clase (excepto __init__ y aquellos que terminan
       con _), será decorado automáticamente con tres decoradores independientes:
       - @typechecked: Validación de tipos en runtime
       - timeit_: Medición de tiempo de ejecución con logging
       - validate_schema: Validación de DataFrames según docstrings
    2. Los métodos previamente decorados como Static methods (@staticmethod)
       se manejan especialmente para asegurar que los decoradores no
       interfieran con su naturaleza. Primero aplicamos los nuevos decoradores
       y luego lo hacemos estático (o cualquier decorador que tuviera).
    3. Loggers específicos para cada método se asignan a la clase con nombres
       dinámicos como log_{nombre_metodo}, permitiendo logging granular.

    Parameters
    ----------
    name : str
        Nombre de la clase siendo creada. (No requerido para el usuario)
    bases : tuple
        Clases base de la clase siendo creada. (No requerido para el usuario)
    dct : dict
        Diccionario conteniendo los atributos y métodos de la clase.
        (No requerido para el usuario)
    log_file : str | None, optional
        Ruta al archivo de log, o None si no se especifica. Default None.
    log_level : str, optional
        Nivel de logging, por defecto 'INFO'.

    Returns
    -------
    new_class : type
        La nueva clase creada con características mejoradas de logging,
        timing y verificación de type hints.
    """

    def __new__(cls,
                name: str,
                bases: tuple,
                dct: dict,
                log_file: str = None,
                log_level: str = 'INFO') -> type:

        log_level = dct.get('log_level', log_level)
        log_file = dct.get('log_file', log_file)

        new_attributes = {}

        def resolve_logger(instance, method_name: str):
            candidates = [
                getattr(instance, "log_file", None) if instance is not None else None,
                os.getenv("METAENGINE_LOG_FILE"),
                log_file,
            ]
            effective_log_file = next((c for c in candidates if c), None)
            effective_level = getattr(instance, "log_level", log_level)
            return setup_logger_for_child(
                parent_name=name,
                child_name=method_name,
                log_file=effective_log_file,
                log_level=effective_level,
                console=False,
            )

        def wrap_callable(method_name: str, func):
            base_fn = func
            is_static = isinstance(base_fn, staticmethod)
            is_classm = isinstance(base_fn, classmethod)
            if is_static or is_classm:
                base_fn = base_fn.__func__

            @functools.wraps(base_fn)
            def _wrapped(*args, **kwargs):
                instance = None if is_static or is_classm else (args[0] if args else None)
                logger = resolve_logger(instance, method_name)
                decorated = typechecked(base_fn)
                decorated = timeit_(decorated, log=logger)
                decorated = validate_schema(decorated, log=logger)
                return decorated(*args, **kwargs)

            if is_static:
                return staticmethod(_wrapped)
            if is_classm:
                return classmethod(_wrapped)
            return _wrapped

        for attr_name, attr_value in dct.items():
            call_condition = callable(attr_value) or isinstance(attr_value, (staticmethod, classmethod))
            init_condition = attr_name != '__init__'
            specific_methods_condition = not attr_name.endswith('_')
            all_conditions = (call_condition and
                              init_condition and
                              specific_methods_condition)

            conditions = {
                'call_condition': call_condition,
                'init_condition': init_condition,
                'specific_methods_condition': specific_methods_condition,
                'is_static': isinstance(attr_value, staticmethod),
                'is_classm': isinstance(attr_value, classmethod),
                'all_conditions': all_conditions
            }

            if all_conditions:
                new_attributes[attr_name] = wrap_callable(attr_name, attr_value)
            else:
                new_attributes[attr_name] = attr_value

        dct.update(new_attributes)
        new_class = super().__new__(cls, name, bases, dct)
        return new_class


# ============================================================================
# SECCIÓN 8: EJEMPLO DE USO
# ============================================================================

"""
EJEMPLO DE USO:

class MiClaseEjemplo(metaclass=MetaEngine, log_level='INFO'):
    '''Clase de ejemplo usando MetaEngine.'''

    def procesar_datos(self, data: pl.DataFrame) -> pl.DataFrame:
        '''
        Procesa un DataFrame de datos.

        Schema:
        -------
        data: pl.DataFrame
            |-- id: int
            |-- nombre: str
            |-- fecha: date (format: %Y-%m-%d)
            Meta instruction: Drop extra columns.

        Parameters
        ----------
        data : pl.DataFrame
            DataFrame con los datos a procesar.

        Returns
        -------
        pl.DataFrame
            DataFrame procesado.
        '''
        # Procesamiento aquí
        return data

    def calcular_metricas(self, valores: list) -> float:
        '''
        Calcula métricas sobre una lista de valores.

        Parameters
        ----------
        valores : list
            Lista de valores numéricos.

        Returns
        -------
        float
            Valor promedio.
        '''
        return sum(valores) / len(valores) if valores else 0.0


# Uso de la clase:
# mi_clase = MiClaseEjemplo()

# Crear un DataFrame de ejemplo
# df = pl.DataFrame({
#     'id': [1, 2, 3],
#     'nombre': ['Alice', 'Bob', 'Charlie'],
#     'fecha': ['2025-01-01', '2025-01-02', '2025-01-03'],
#     'columna_extra': ['x', 'y', 'z']  # Esta será eliminada por validate_schema
# })

# Procesar datos - automáticamente:
# - Validará tipos de parámetros y retorno (@typechecked)
# - Medirá tiempo de ejecución (timeit_)
# - Validará el schema del DataFrame (validate_schema)
# - Eliminará 'columna_extra' según meta instruction
# - Logeará todas las acciones
# resultado = mi_clase.procesar_datos(data=df)

# Calcular métricas - automáticamente:
# - Validará tipos (@typechecked)
# - Medirá tiempo de ejecución (timeit_)
# - Logeará inicio y fin del proceso
# promedio = mi_clase.calcular_metricas([1, 2, 3, 4, 5])

# Acceso a loggers individuales por método:
# mi_clase.log_procesar_datos.info("Log específico del método")
# mi_clase.log_calcular_metricas.debug("Debug del método")


CARACTERÍSTICAS AUTOMÁTICAS AL USAR MetaEngine:

1. Type Checking (@typechecked):
   - Validación automática de tipos en runtime
   - Verifica tipos de parámetros y valores de retorno
   - Genera errores claros si los tipos no coinciden
   - Aplicado INDEPENDIENTEMENTE antes de timing

2. Logging Jerárquico:
   - Cada método obtiene su propio logger: log_{nombre_metodo}
   - Estructura: NombreClase.nombre_metodo
   - Niveles configurables: INFO, DEBUG, WARNING, ERROR

3. Medición de Tiempo (timeit_):
   - Todos los métodos (excepto __init__ y _privados) se cronometran
   - Logs automáticos: "Initiating process." y "Done. Total time: X seconds"
   - NO incluye @typechecked internamente (se aplica por separado)

4. Validación de Schemas (validate_schema):
   - DataFrames se validan contra schemas definidos en docstrings
   - Conversión automática de tipos
   - Opción de eliminar columnas extra con meta instruction
   - Logging de columnas extra encontradas

5. Manejo de Decoradores:
   - Respeta @staticmethod y @classmethod
   - Aplica decoradores en orden correcto:
     1. @typechecked (primero - validación de tipos)
     2. timeit_ (segundo - medición de tiempo)
     3. validate_schema (tercero - validación de DataFrames)

ORDEN DE APLICACIÓN DE DECORADORES:

Cuando defines un método en una clase con MetaEngine:

    def mi_metodo(self, x: int) -> int:
        return x * 2

MetaEngine lo transforma en algo equivalente a:

    @staticmethod  # Si era @staticmethod originalmente
    @validate_schema(..., log=log_mi_metodo)
    @timeit_(..., log=log_mi_metodo)
    @typechecked
    def mi_metodo(self, x: int) -> int:
        return x * 2

Esto significa que:
- Primero se validan tipos (typechecked)
- Luego se mide tiempo (timeit_)
- Finalmente se validan schemas (validate_schema)
- Y se respetan decoradores originales como @staticmethod
"""
