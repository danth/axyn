from numpy import dtype, int8, float16, float32, ndarray
import sys
from typing import Sequence, Union, Literal, overload


Vector = ndarray[tuple[int], dtype[Union[int8, float16, float32]]]
FLT_MAX = sys.float_info.max
INT_MIN = -9223372036854775808


# Based on https://github.com/yahoojapan/NGT/blob/d7169ce5c79761f63522c2fb34db3638c64537a8/python/src/ngtpy.cpp


__version__: str


def create(
    path: str,
    dimension: int,
    *,
    edge_size_for_creation: int = 10,
    edge_size_for_search: int = 40,
    distance_type: Union[
        Literal["L1"],
        Literal["L2"],
        Literal["Normalized L2"],
        Literal["Hamming"],
        Literal["Jaccard"],
        Literal["Sparse Jaccard"],
        Literal["Angle"],
        Literal["Normalized Angle"],
        Literal["Cosine"],
        Literal["Normalized Cosine"],
        Literal["Normalized L2"],
        Literal["Inner Product"],
    ] = "L2",
    object_type: Union[
        Literal["Float"],
        Literal["float"],
        Literal["Byte"],
        Literal["byte"],
        Literal["Float16"],
        Literal["float16"],
    ] = "Float",
    graph_type: Union[
        Literal["ANNG"],
        Literal["IANNG"],
        Literal["RANNG"],
        Literal["RIANNG"],
    ] = "ANNG",
) -> None:
    ...


class Index:
    def __init__(
        self,
        path: str,
        *,
        read_only: bool = False,
        zero_based_numbering: bool = True,
        tree_disabled: bool = False,
        log_disabled: bool = False,
    ) -> None:
        ...


    @overload
    def search(
        self,
        query: Vector,
        *,
        size: int = 0,
        epsilon: float = -FLT_MAX,
        edge_size: int = INT_MIN,
        expected_accuracy: float = -FLT_MAX,
        with_distance: Literal[False],
    ) -> Sequence[int]:
        ...

    @overload
    def search(
        self,
        query: Vector,
        *,
        size: int = 0,
        epsilon: float = -FLT_MAX,
        edge_size: int = INT_MIN,
        expected_accuracy: float = -FLT_MAX,
        with_distance: Literal[True],
    ) -> Sequence[tuple[int, float]]:
        ...

    @overload
    def search(
        self,
        query: Vector,
        *,
        size: int = 0,
        epsilon: float = -FLT_MAX,
        edge_size: int = INT_MIN,
        expected_accuracy: float = -FLT_MAX,
    ) -> Sequence[tuple[int, float]]:
        ...

    def search(
        self,
        query: Vector,
        *,
        size: int = 0,
        epsilon: float = -FLT_MAX,
        edge_size: int = INT_MIN,
        expected_accuracy: float = -FLT_MAX,
        with_distance: bool = True,
    ) -> Union[
        Sequence[int],
        Sequence[tuple[int, float]],
    ]:
        ...

    @overload
    def linear_search(
        self,
        query: Vector,
        *,
        size: int = 0,
        with_distance: Literal[False],
    ) -> Sequence[int]:
        ...

    @overload
    def linear_search(
        self,
        query: Vector,
        *,
        size: int = 0,
        with_distance: Literal[True],
    ) -> Sequence[tuple[int, float]]:
        ...

    @overload
    def linear_search(
        self,
        query: Vector,
        *,
        size: int = 0,
    ) -> Sequence[tuple[int, float]]:
        ...

    def linear_search(
        self,
        query: Vector,
        *,
        size: int = 0,
        with_distance: bool = True,
    ) -> Union[
        Sequence[int],
        Sequence[tuple[int, float]],
    ]:
        ...

    def batch_search(
        self,
        query: Sequence[float],
        results: BatchResults,
        *,
        size: int = 0,
        with_distance: bool = True,
    ) -> None:
        ...

    def get_num_of_distance_computations(self) -> int:
        ...

    def save(self) -> None:
        ...

    def close(self) -> None:
        ...

    def remove(self, object_id: int) -> None:
        ...

    def build_index(
        self,
        *,
        num_threads: int = 8,
        target_size_of_graph: int = 0,
    ) -> None:
        ...

    def get_num_of_objects(self) -> int:
        ...

    def get_size_of_object_repository(self) -> int:
        ...

    def get_size_of_graph_repository(self) -> int:
        ...

    def get_object(self, object_id: int) -> Vector:
        ...

    def batch_insert(
        self,
        objects: Sequence[Vector],
        *,
        num_threads: int = 8,
        append: bool = True,
        refinement: bool = False,
        debug: bool = False,
    ) -> None:
        ...

    def insert(
        self,
        object: Vector,
        *,
        debug: bool = False,
    ) -> int:
        ...

    def refine_anng(
        self,
        *,
        epsilon: float = 0.1,
        expected_accuracy: float = 0,
        num_of_edges: int = 0,
        num_of_explored_edges: int = INT_MIN,
        batch_size: int = 10000,
    ) -> None:
        ...

    def set(
        self,
        *,
        num_of_search_objects: int = 0,
        search_radius: float = -FLT_MAX,
        epsilon: float = -FLT_MAX,
        edge_size: int = INT_MIN,
        expected_accuracy: float = -FLT_MAX,
        result_expansion: float = -FLT_MAX,
    ) -> None:
        ...

    def export_index(self, path: str) -> None:
        ...

    def import_index(self, path: str) -> None:
        ...


class BatchResults:
    def __init__(self) -> None:
        ...

    def get(self, position: int) -> Vector:
        ...

    def get_ids(self) -> Sequence[int]:
        ...

    def get_indexed_ids(self) -> Sequence[int]:
        ...

    def get_indexed_distances(self) -> Sequence[float]:
        ...

    def get_index(self) -> Sequence[int]:
        ...

    def get_size(self) -> int:
        ...
