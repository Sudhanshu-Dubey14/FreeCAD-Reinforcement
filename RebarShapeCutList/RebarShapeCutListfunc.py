# -*- coding: utf-8 -*-
# ***************************************************************************
# *                                                                         *
# *   Copyright (c) 2020 - Suraj <dadralj18@gmail.com>                      *
# *                                                                         *
# *   This program is free software; you can redistribute it and/or modify  *
# *   it under the terms of the GNU Lesser General Public License (LGPL)    *
# *   as published by the Free Software Foundation; either version 2 of     *
# *   the License, or (at your option) any later version.                   *
# *   for detail see the LICENCE text file.                                 *
# *                                                                         *
# *   This program is distributed in the hope that it will be useful,       *
# *   but WITHOUT ANY WARRANTY; without even the implied warranty of        *
# *   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the         *
# *   GNU Library General Public License for more details.                  *
# *                                                                         *
# *   You should have received a copy of the GNU Library General Public     *
# *   License along with this program; if not, write to the Free Software   *
# *   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  *
# *   USA                                                                   *
# *                                                                         *
# ***************************************************************************

__title__ = "Rebar Dimensioning Object"
__author__ = "Suraj"
__url__ = "https://www.freecadweb.org"


import math
from typing import Union, List, Tuple
from xml.etree import ElementTree

import Draft
import DraftGeomUtils
import DraftVecUtils
import FreeCAD
import Part
import WorkingPlane

from ReinforcementDrawing.ReinforcementDrawingfunc import (
    getRebarsSpanAxis,
    getSVGPlaneFromAxis,
    getProjectionToSVGPlane,
    getRoundCornerSVG,
    getRebarColor,
)
from SVGfunc import (
    getSVGRootElement,
    getPointSVG,
    getLineSVG,
    getSVGTextElement,
    getSVGRectangle,
)


def getBaseRebarsList(one_rebar_per_mark: bool = True) -> list:
    """
    Parameters
    ----------
    one_rebar_per_mark: bool
        If it is set to True, then only single rebar will be returned per mark.
        Otherwise all ArchRebar and rebar2.BaseRebar objects will be returned
        from active document.
        Default is True.

    Returns
    -------
    list of <ArchRebar> and <rebar2.BaseRebar>
        The list of ArchRebar and rebar2.BaseRebar objects from active document.
    """
    if not FreeCAD.ActiveDocument:
        return []

    rebars = []
    mark_list = []

    arch_rebars = Draft.get_objects_of_type(
        FreeCAD.ActiveDocument.Objects, "Rebar"
    )
    if one_rebar_per_mark:
        for rebar in arch_rebars:
            if rebar.Mark and rebar.Mark not in mark_list:
                rebars.append(rebar)
                mark_list.append(rebar.Mark)
    else:
        rebars.extend(arch_rebars)

    base_rebars = Draft.get_objects_of_type(
        FreeCAD.ActiveDocument.Objects, "RebarShape"
    )
    if base_rebars and isinstance(base_rebars[0].MarkNumber, int):
        base_rebars = sorted(base_rebars, key=lambda x: x.MarkNumber)
    if one_rebar_per_mark:
        for rebar in base_rebars:
            if str(rebar.MarkNumber) and str(rebar.MarkNumber) not in mark_list:
                rebars.append(rebar)
                mark_list.append(str(rebar.MarkNumber))
    else:
        rebars.extend(base_rebars)

    return rebars


def getVertexesMinMaxXY(
    vertex_list: List[Part.Vertex], view_plane: WorkingPlane.Plane
) -> Tuple[float, float, float, float]:
    """Returns min_x, min_y, max_x, max_y for vertex_list, when each vertex
    is projected on view_plane.

    Parameters
    ----------
    vertex_list: list of <Part.Vertex>
        Input vertex list.
    view_plane: WorkingPlane.Plane
        view plane to project vertexes on it.

    Returns
    -------
    min_x: float
        The minimum x_coordinate value when each vertex is projected on
        view_plane.
    min_y: float
        The minimum y_coordinate value when each vertex is projected on
        view_plane.
    max_x: float
        The maximum x_coordinate value when each vertex is projected on
        view_plane.
    max_y: float
        The maximum y_coordinate value when each vertex is projected on
        view_plane.
    """
    point = getProjectionToSVGPlane(vertex_list[0].Point, view_plane)
    min_x = point.x
    min_y = point.y
    max_x = point.x
    max_y = point.y
    for vertex in vertex_list[1:]:
        point = getProjectionToSVGPlane(vertex.Point, view_plane)
        min_x = min(point.x, min_x)
        min_y = min(point.y, min_y)
        max_x = max(point.x, max_x)
        max_y = max(point.y, max_y)
    return min_x, min_y, max_x, max_y


def getRebarShapeSVG(
    rebar,
    view_direction: Union[FreeCAD.Vector, WorkingPlane.Plane] = FreeCAD.Vector(
        0, 0, 0
    ),
    include_mark: bool = True,
    rebar_stroke_width: float = 0.35,
    rebar_color_style: str = "shape color",
    dimension_font_family: str = "DejaVu Sans",
    dimension_font_size: float = 2,
    scale: float = 1,
    max_height: float = 0,
    max_width: float = 0,
) -> ElementTree.Element:
    """Generate and return rebar shape svg.

    Parameters
    ----------
    rebar: <ArchRebar._Rebar> or <rebar2.BaseRebar>
        Rebar to generate its shape svg.
    view_direction: FreeCAD.Vector or WorkingPlane.Plane, optional
        The view point direction for rebar shape.
        Default is FreeCAD.Vector(0, 0, 0) to automatically choose
        view_direction.
    include_mark: bool, optional
        If it is set to True, then rebar.Mark will be included in rebar shape
        svg.
        Default is True.
    rebar_stroke_width: float, optional
        The stroke-width of rebar in svg.
        Default is 0.35
    rebar_color_style: {"shape color", "color_name", "hex_value_of_color"}
        The color style of rebar.
        "shape color" means select color of rebar shape.
    dimension_font_family: str, optional
        The font-family of dimension text.
        Default is "DejaVu Sans".
    dimension_font_size: float, optional
        The font-size of dimension text.
        Default is 2
    scale: float, optional
        The scale value to scale rebar svg. The scale parameter helps to
        scale down rebar_stroke_width and dimension_font_size to make them
        resolution independent.
        if max_height or max_width is set to non-zero value, then scale
        parameter will be ignored.
        Default is 1
    max_height: float, optional
        The maximum height of rebar shape svg.
        Default is 0 to set rebar shape svg height based on scale parameter.
    max_width: float, optional
        The maximum width of rebar shape svg.
        Default is 0 to set rebar shape svg width based on scale parameter.

    Returns
    -------
    ElementTree.Element
        The generated rebar shape svg.
    """
    if isinstance(view_direction, FreeCAD.Vector):
        if DraftVecUtils.isNull(view_direction):
            view_direction = getRebarsSpanAxis(rebar)
        view_plane = getSVGPlaneFromAxis(view_direction)
    elif isinstance(view_direction, WorkingPlane.Plane):
        view_plane = view_direction
    else:
        FreeCAD.Console.PrintError(
            "Invalid view_direction type. Supported view_direction types: "
            "FreeCAD.Vector, WorkingPlane.Plane\n"
        )
        return ElementTree.Element("g")

    # Get user preferred unit precision
    precision: int = FreeCAD.ParamGet(
        "User parameter:BaseApp/Preferences/Units"
    ).GetInt("Decimals")

    # Create required svg elements
    svg = getSVGRootElement()
    rebar_color = getRebarColor(rebar, rebar_color_style)
    rebar_shape_svg = ElementTree.Element("g", attrib={"id": str(rebar.Name)})
    svg.append(rebar_shape_svg)
    rebar_edges_svg = ElementTree.Element("g")
    edge_dimension_svg = ElementTree.Element("g")
    rebar_shape_svg.extend([rebar_edges_svg, edge_dimension_svg])

    # Get basewire and fillet_basewire (basewire with round edges)
    basewire = rebar.Base.Shape.Wires[0].copy()
    fillet_radius = rebar.Rounding * rebar.Diameter.Value
    if fillet_radius:
        fillet_basewire = DraftGeomUtils.filletWire(basewire, fillet_radius)
    else:
        fillet_basewire = basewire

    (
        rebar_shape_min_x,
        rebar_shape_min_y,
        rebar_shape_max_x,
        rebar_shape_max_y,
    ) = getVertexesMinMaxXY(fillet_basewire.Vertexes, view_plane)

    # Apply max_height and max_width of rebar shape svg And calculate scaling
    # factor
    rebar_shape_height = rebar_shape_max_y - rebar_shape_min_y
    rebar_shape_width = rebar_shape_max_x - rebar_shape_min_x
    h_scaling_factor = v_scaling_factor = scale
    if max_height:
        v_scaling_factor = (
            max_height
            - dimension_font_size * (4 if include_mark else 2)
            - 2 * rebar_stroke_width
        ) / rebar_shape_height
    if max_width:
        h_scaling_factor = (
            max_width - 2 * dimension_font_size - 2 * rebar_stroke_width
        ) / rebar_shape_width
    scale = min(h_scaling_factor, v_scaling_factor)
    svg_height = (
        rebar_shape_height * scale
        + dimension_font_size * (4 if include_mark else 2)
        - 2 * rebar_stroke_width
    )
    svg_width = (
        rebar_shape_width * scale
        + 2 * dimension_font_size
        - 2 * rebar_stroke_width
    )

    # Move (min_x, min_y) point in svg plane to (0, 0) so that entire basewire
    # should be visible in svg view box and apply required scaling
    translate_x = round(
        -(
            rebar_shape_min_x
            - (dimension_font_size + rebar_stroke_width) / scale
        )
    )
    translate_y = round(
        -(
            rebar_shape_min_y
            - (3 if include_mark else 1) * dimension_font_size / scale
            - rebar_stroke_width / scale
        )
    )
    rebar_shape_svg.set(
        "transform",
        "scale({}) translate({} {})".format(scale, translate_x, translate_y),
    )

    svg.set("width", "{}mm".format(round(svg_width)))
    svg.set("height", "{}mm".format(round(svg_height)))
    svg.set("viewBox", "0 0 {} {}".format(round(svg_width), round(svg_height)))

    # Scale down rebar_stroke_width and dimension_font_size to make them
    # resolution independent
    rebar_stroke_width /= scale
    dimension_font_size /= scale

    # Include rebar.Mark in rebar shape svg
    if include_mark:
        if hasattr(rebar, "Mark"):
            mark = rebar.Mark
        elif hasattr(rebar, "MarkNumber"):
            mark = rebar.MarkNumber
        else:
            mark = ""
        rebar_shape_svg.append(
            getSVGTextElement(
                mark,
                rebar_shape_min_x,
                rebar_shape_min_y - 1.5 * dimension_font_size,
                dimension_font_family,
                1.5 * dimension_font_size,
            )
        )

    edges = Part.__sortEdges__(fillet_basewire.Edges)
    straight_edges = Part.__sortEdges__(basewire.Edges)
    current_straight_edge_index = 0
    for edge in edges:
        if DraftGeomUtils.geomType(edge) == "Line":
            p1 = getProjectionToSVGPlane(edge.Vertexes[0].Point, view_plane)
            p2 = getProjectionToSVGPlane(edge.Vertexes[1].Point, view_plane)
            # Create Edge svg
            if round(p1.x) == round(p2.x) and round(p1.y) == round(p2.y):
                edge_svg = getPointSVG(
                    p1, radius=2 * rebar_stroke_width, fill=rebar_color
                )
            else:
                edge_svg = getLineSVG(p1, p2, rebar_stroke_width, rebar_color)
            # Create edge dimension svg
            mid_point = FreeCAD.Vector((p1.x + p2.x) / 2, (p1.y + p2.y) / 2)
            dimension_rotation = (
                math.degrees(math.atan((p2.y - p1.y) / (p2.x - p1.x)))
                if round(p2.x) != round(p1.x)
                else -90
            )
            edge_length = str(
                round(
                    straight_edges[current_straight_edge_index].Length,
                    precision,
                )
            )
            if "." in edge_length:
                edge_length = edge_length.rstrip("0").rstrip(".")
            edge_dimension_svg.append(
                getSVGTextElement(
                    edge_length,
                    mid_point.x,
                    mid_point.y - rebar_stroke_width * 2,
                    dimension_font_family,
                    dimension_font_size,
                    "middle",
                )
            )
            edge_dimension_svg[-1].set(
                "transform",
                "rotate({} {} {})".format(
                    dimension_rotation, round(mid_point.x), round(mid_point.y)
                ),
            )
            current_straight_edge_index += 1
        elif DraftGeomUtils.geomType(edge) == "Circle":
            p1 = getProjectionToSVGPlane(edge.Vertexes[0].Point, view_plane)
            p2 = getProjectionToSVGPlane(edge.Vertexes[1].Point, view_plane)
            if round(p1.x) == round(p2.x) or round(p1.y) == round(p2.y):
                edge_svg = getLineSVG(p1, p2, rebar_stroke_width, rebar_color)
            else:
                edge_svg = getRoundCornerSVG(
                    edge,
                    rebar.Rounding * rebar.Diameter.Value,
                    view_plane,
                    rebar_stroke_width,
                    rebar_color,
                )
        else:
            edge_svg = ElementTree.Element("g")
        rebar_edges_svg.append(edge_svg)

    return svg


def getRebarShapeCutList(
    base_rebars_list=None,
    view_directions: List[
        Union[FreeCAD.Vector, WorkingPlane.Plane]
    ] = FreeCAD.Vector(0, 0, 0),
    include_mark: bool = True,
    rebars_stroke_width: float = 0.35,
    rebars_color_style: str = "shape color",
    dimension_font_family: str = "DejaVu Sans",
    dimension_font_size: float = 2,
    row_height: float = 40,
    width: float = 60,
) -> ElementTree.Element:
    """Generate and return rebar shape cut list svg.

    Parameters
    ----------
    base_rebars_list: list of <ArchRebar._Rebar> or <rebar2.BaseRebar>
        Rebars list to generate RebarShape cut list.
    view_directions: list of FreeCAD.Vector or WorkingPlane.Plane, optional
        The view point directions for each rebar shape.
        Default is FreeCAD.Vector(0, 0, 0) to automatically choose
        view_directions.
    include_mark: bool, optional
        If it is set to True, then rebar.Mark will be included for each rebar
        shape in rebar shape cut list svg.
        Default is True.
    rebars_stroke_width: float, optional
        The stroke-width of rebars in rebar shape cut list svg.
        Default is 0.35
    rebars_color_style: {"shape color", "color_name", "hex_value_of_color"}
        The color style of rebars.
        "shape color" means select color of rebar shape.
    dimension_font_family: str, optional
        The font-family of dimension text.
        Default is "DejaVu Sans".
    dimension_font_size: float, optional
        The font-size of dimension text.
        Default is 2
    row_height: float, optional
        The height of each row of rebar shape in rebar shape cut list.
        Default is 40
    width: float, optional
        The width of rebar shape cut list.

    Returns
    -------
    ElementTree.Element
        The rebar shape cut list svg.
    """
    if base_rebars_list is None:
        base_rebars_list = getBaseRebarsList()

    if not base_rebars_list:
        return ElementTree.Element(
            "svg",
            height="{}mm".format(row_height),
            width="{}mm".format(width),
            viewBox="0 0 {} {}".format(width, row_height),
        )

    if isinstance(view_directions, FreeCAD.Vector):
        view_directions = len(base_rebars_list) * [view_directions]
    elif isinstance(view_directions, list):
        if len(view_directions) < len(base_rebars_list):
            view_directions.extend(
                (len(base_rebars_list) - len(view_directions))
                * FreeCAD.Vector(0, 0, 0)
            )

    rebar_shape_max_height = row_height
    if include_mark:
        rebar_shape_max_height -= 2 * dimension_font_size

    svg = getSVGRootElement()
    for i, rebar in enumerate(base_rebars_list):
        rebar_svg = getRebarShapeSVG(
            rebar,
            view_directions[i],
            False,
            rebars_stroke_width,
            rebars_color_style,
            dimension_font_family,
            dimension_font_size,
            max_height=rebar_shape_max_height,
            max_width=width,
        )
        # Center align rebar shape svg horizontally and vertically in row cell
        rebar_shape_svg_width = float(rebar_svg.get("width").rstrip("mm"))
        rebar_shape_svg_height = float(rebar_svg.get("height").rstrip("mm"))
        rebar_shape_svg = ElementTree.Element(
            "g",
            transform="translate({} {})".format(
                (width - rebar_shape_svg_width) / 2,
                (rebar_shape_max_height - rebar_shape_svg_height) / 2
                + (2 * dimension_font_size if include_mark else 0),
            ),
        )
        rebar_shape_svg.append(
            rebar_svg.find("./g[@id='{}']".format(rebar.Name))
        )
        # Create row border svg
        row_border_svg = getSVGRectangle(
            0, 0, width, row_height, element_id="row_{}".format(i)
        )
        # Create row svg and translate it vertically to it position
        row_svg = ElementTree.Element(
            "g", transform="translate({} {})".format(0, i * row_height),
        )
        row_svg.extend([row_border_svg, rebar_shape_svg])
        # Include mark label in each row
        if include_mark:
            if hasattr(rebar, "Mark"):
                mark = rebar.Mark
            elif hasattr(rebar, "MarkNumber"):
                mark = rebar.MarkNumber
            else:
                mark = ""
            row_svg.append(
                getSVGTextElement(
                    mark,
                    2,
                    2 * dimension_font_size,
                    dimension_font_family,
                    1.5 * dimension_font_size,
                )
            )
        svg.append(row_svg)

    svg.set("width", "{}mm".format(width))
    svg.set("height", "{}mm".format(row_height * len(base_rebars_list)))
    svg.set(
        "viewBox", "0 0 {} {}".format(width, row_height * len(base_rebars_list))
    )

    return svg