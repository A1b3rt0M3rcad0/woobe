from __future__ import annotations

from collections.abc import Iterable, Mapping


def strongly_connected_components(graph: Mapping[str, Iterable[str]]) -> tuple[tuple[str, ...], ...]:
    """Return cyclic strongly connected components in deterministic order."""

    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlinks: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    nodes = sorted(set(graph) | {target for targets in graph.values() for target in targets})

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in sorted(graph.get(node, ())):
            if target not in indices:
                visit(target)
                lowlinks[node] = min(lowlinks[node], lowlinks[target])
            elif target in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[target])

        if lowlinks[node] != indices[node]:
            return

        component: list[str] = []
        while stack:
            item = stack.pop()
            on_stack.remove(item)
            component.append(item)
            if item == node:
                break

        component.sort()
        if len(component) > 1:
            components.append(tuple(component))
        elif component and component[0] in set(graph.get(component[0], ())):
            components.append(tuple(component))

    for node in nodes:
        if node not in indices:
            visit(node)

    return tuple(sorted(components))
