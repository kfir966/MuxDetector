"""Reduced ordered binary decision diagram implementation."""

from __future__ import annotations

from dataclasses import dataclass

from .mux_analysis_limit_error import MuxAnalysisLimitError


_MAX_SYMBOLIC_VARIABLES = 128
_MAX_BDD_NODES = 100_000
_MAX_BDD_CACHE_ENTRIES = 200_000
_FALSE_NODE_ID = -1
_TRUE_NODE_ID = -2


@dataclass(frozen=True)
class _DecisionNode:
    """Store an input test and the node IDs for its 0 and 1 outcomes."""

    variable_index: int
    zero_child_node_id: int
    one_child_node_id: int


class BDD:
    """Build a reduced ordered binary decision diagram (ROBDD).

    A node asks whether an input is 0 or 1 and follows the matching branch.
    A fixed input order lets identical subgraphs be shared; tests with matching
    branches are removed. 
    Node ID -1 means false; node ID -2 means true. Decision node IDs start at
    0 and refer to `_DecisionNode` records stored by this class.

    The MUX analyzer uses this graph only above 16 distinct input names, to
    find which inputs can affect the result before building a truth table.
    """

    _TERMINAL_ORDER_INDEX = _MAX_SYMBOLIC_VARIABLES

    def __init__(self) -> None:
        self._decision_nodes: list[_DecisionNode] = []
        self._node_id_by_definition: dict[_DecisionNode, int] = {}
        self._operator_result_cache: dict[tuple[str, int, int], int] = {}
        self._negation_cache = {
            _FALSE_NODE_ID: _TRUE_NODE_ID,
            _TRUE_NODE_ID: _FALSE_NODE_ID,
        }

    def _make_or_reuse_node(
        self,
        variable_index: int,
        zero_child_node_id: int,
        one_child_node_id: int,
    ) -> int:
        """Reuse an equivalent node or create one, omitting redundant tests."""
        if zero_child_node_id == one_child_node_id:
            return zero_child_node_id

        definition = _DecisionNode(
            variable_index,
            zero_child_node_id,
            one_child_node_id,
        )
        if definition in self._node_id_by_definition:
            return self._node_id_by_definition[definition]
        if len(self._decision_nodes) >= _MAX_BDD_NODES:
            raise MuxAnalysisLimitError(
                f"symbolic support check exceeded {_MAX_BDD_NODES} nodes"
            )
        node_id = len(self._decision_nodes) # node_id is also the index
        self._decision_nodes.append(definition)
        self._node_id_by_definition[definition] = node_id
        return node_id

    def _get_decision_node(self, node_id: int) -> _DecisionNode:
        """Look up a decision node by its list-index ID."""
        return self._decision_nodes[node_id]

    def make_constant_node(self, value: int) -> int:
        """Return the node ID for a Boolean constant, 0 or 1."""
        if value == 0:
            return _FALSE_NODE_ID
        if value == 1:
            return _TRUE_NODE_ID
        raise ValueError(f"Boolean constant must be 0 or 1, got {value!r}")

    def make_variable_node(self, variable_index: int) -> int:
        """Test this zero-based input index: its 0 branch is false, its 1 true."""
        if variable_index >= _MAX_SYMBOLIC_VARIABLES:
            raise MuxAnalysisLimitError(
                "symbolic support check is limited to "
                f"{_MAX_SYMBOLIC_VARIABLES} variables"
            )
        return self._make_or_reuse_node(
            variable_index,
            _FALSE_NODE_ID,
            _TRUE_NODE_ID,
        )

    def negate_node(self, node_id: int) -> int:
        """Return the node ID for the opposite result."""
        if node_id in self._negation_cache:
            return self._negation_cache[node_id]
        decision_node = self._get_decision_node(node_id)
        negated_node_id = self._make_or_reuse_node(
            decision_node.variable_index,
            self.negate_node(decision_node.zero_child_node_id),
            self.negate_node(decision_node.one_child_node_id),
        )
        self._negation_cache[node_id] = negated_node_id
        self._negation_cache[negated_node_id] = node_id
        return negated_node_id

    def apply_operator(
        self, operator: str, left_node: int, right_node: int
    ) -> int:
        """Combine two node IDs with AND, OR, or XOR and return the result node.

        The graph is split at the earliest variable tested by either node.
        """
        if operator not in ("AND", "OR", "XOR"):
            raise ValueError(f"unsupported Boolean operator {operator!r}")

        left_node_id = left_node
        right_node_id = right_node
        # assuring right is greater - assuring commutativity of AND, OR, XOR and reducing cache size
        if left_node_id > right_node_id:
            left_node_id, right_node_id = right_node_id, left_node_id
        cache_key = (operator, left_node_id, right_node_id)
        if cache_key in self._operator_result_cache:
            return self._operator_result_cache[cache_key]

        simple_result = self._try_apply_simple_case(
            operator, left_node_id, right_node_id
        )
        if simple_result is not None:
            return simple_result

        # take earliest index
        variable_index = min(
            self._variable_index_for_node(left_node_id),
            self._variable_index_for_node(right_node_id),
        )
        left_zero_node_id, left_one_node_id = self._branches_for_variable(
            left_node_id, variable_index
        )
        right_zero_node_id, right_one_node_id = self._branches_for_variable(
            right_node_id, variable_index
        )
        result_node_id = self._make_or_reuse_node(
            variable_index,
            self.apply_operator(operator, left_zero_node_id, right_zero_node_id),
            self.apply_operator(operator, left_one_node_id, right_one_node_id),
        )

        if len(self._operator_result_cache) >= _MAX_BDD_CACHE_ENTRIES:
            raise MuxAnalysisLimitError(
                "symbolic support check exceeded "
                f"{_MAX_BDD_CACHE_ENTRIES} cached operations"
            )
        self._operator_result_cache[cache_key] = result_node_id
        return result_node_id

    def _try_apply_simple_case(
        self, operator: str, left_node_id: int, right_node_id: int
    ) -> int | None:
        """Resolve terminal operands or simple Boolean identities, if possible."""
        terminal_result = self._apply_to_terminal_nodes(
            operator, left_node_id, right_node_id
        )
        if terminal_result is not None:
            return terminal_result
        return self._apply_boolean_identity(operator, left_node_id, right_node_id)

    @staticmethod
    def _apply_to_terminal_nodes(
        operator: str, left_node_id: int, right_node_id: int
    ) -> int | None:
        """Apply an operator directly when both nodes are false or true."""
        if (
            not BDD._is_decision_node_id(left_node_id)
            and not BDD._is_decision_node_id(right_node_id)
        ):
            left_value = left_node_id == _TRUE_NODE_ID
            right_value = right_node_id == _TRUE_NODE_ID
            if operator == "AND":
                result_value = left_value and right_value
            elif operator == "OR":
                result_value = left_value or right_value
            else:
                result_value = left_value != right_value
            return _TRUE_NODE_ID if result_value else _FALSE_NODE_ID
        return None

    def _apply_boolean_identity(
        self, operator: str, left_node_id: int, right_node_id: int
    ) -> int | None:
        """
        Resolve identities such as false AND x or x XOR x.
        Assuming left_node_id <= right_node_id, so commutative identities can be handled.
        """
        if operator == "AND":
            if left_node_id == _FALSE_NODE_ID:
                return _FALSE_NODE_ID
            if left_node_id == _TRUE_NODE_ID:
                return right_node_id
            if left_node_id == right_node_id:
                return left_node_id
        elif operator == "OR":
            if left_node_id == _TRUE_NODE_ID:
                return _TRUE_NODE_ID
            if left_node_id == _FALSE_NODE_ID:
                return right_node_id
            if left_node_id == right_node_id:
                return left_node_id
        else:
            if left_node_id == _FALSE_NODE_ID:
                return right_node_id
            if left_node_id == _TRUE_NODE_ID:
                return self.negate_node(right_node_id)
            if left_node_id == right_node_id:
                return _FALSE_NODE_ID
        return None

    def _variable_index_for_node(self, node_id: int) -> int:
        """Return a node's input index; place terminals after all input nodes."""
        if not self._is_decision_node_id(node_id):
            return self._TERMINAL_ORDER_INDEX
        return self._get_decision_node(node_id).variable_index

    def _branches_for_variable(
        self, node_id: int, variable_index: int
    ) -> tuple[int, int]:
        """Return 0/1 child IDs, or the same node twice if it tests another input."""
        if self._is_decision_node_id(node_id):
            decision_node = self._get_decision_node(node_id)
            if decision_node.variable_index == variable_index:
                return (
                    decision_node.zero_child_node_id,
                    decision_node.one_child_node_id,
                )
        return node_id, node_id

    @staticmethod
    def _is_decision_node_id(node_id: int) -> bool:
        return node_id >= 0

    def find_active_variables(self, root_node: int) -> set[int]:
        """Return input indices that can affect the result at this root node."""
        variables: set[int] = set()
        visited_node_ids: set[int] = set()
        pending_node_ids = [root_node]
        while pending_node_ids:
            node_id = pending_node_ids.pop()
            if (
                not self._is_decision_node_id(node_id)
                or node_id in visited_node_ids
            ):
                continue
            
            visited_node_ids.add(node_id)
            decision_node = self._get_decision_node(node_id)
            variables.add(decision_node.variable_index)
            pending_node_ids.extend(
                (
                    decision_node.zero_child_node_id,
                    decision_node.one_child_node_id,
                )
            )
        return variables
