from qgis.core import QgsSymbol, Qgis, QgsMarkerSymbol, QgsRendererRange,\
    QgsLineSymbol, QgsFillSymbol, QgsGraduatedSymbolRenderer, \
    QgsProject, QgsRendererCategory, QgsCategorizedSymbolRenderer, \
    QgsTextFormat, QgsPalLayerSettings, QgsTextBufferSettings, \
    QgsVectorLayerSimpleLabeling, QgsRasterLayer, QgsCoordinateReferenceSystem, \
    QgsRectangle
from PyQt5.QtGui import QColor, QFont
import numpy as np
import matplotlib.pyplot as plt
from ..support_scripts.RG import rg
__author__ = 'Axel'


def set_label(layer, field_label):
    """Function that sets the label to a field value. Inspiration found at:
    https://gis.stackexchange.com/questions/277106/loading-labels-from-python-script-in-qgis
    :param layer valid qgis layer.
    :param field_label str with the field """
    layer_settings = QgsPalLayerSettings()
    text_format = QgsTextFormat()

    text_format.setFont(QFont("Arial", 12))
    text_format.setSize(12)

    buffer_settings = QgsTextBufferSettings()
    buffer_settings.setEnabled(True)
    buffer_settings.setSize(0.10)
    buffer_settings.setColor(QColor("black"))

    text_format.setBuffer(buffer_settings)
    layer_settings.setFormat(text_format)
    layer_settings.fieldName = field_label
    layer_settings.placement = 4

    layer_settings.enabled = True

    layer_settings = QgsVectorLayerSimpleLabeling(layer_settings)
    layer.setLabelsEnabled(True)
    layer.setLabeling(layer_settings)
    layer.triggerRepaint()


def set_zoom(iface, extra_extent):
    zoom_extent = QgsRectangle()
    for layer in QgsProject.instance().mapLayers().values():
        if 'xyz&url' not in layer.source():
            zoom_extent.combineExtentWith(layer.extent())
    if zoom_extent.center().x() != 0.0:
        wgsCRS = QgsCoordinateReferenceSystem(4326)
        QgsProject.instance().setCrs(wgsCRS)
        zoom_extent.scale(extra_extent)
        iface.mapCanvas().setExtent(zoom_extent)
        iface.mapCanvas().refresh()
        wgsCRS = QgsCoordinateReferenceSystem(3857)
        QgsProject.instance().setCrs(wgsCRS)


def add_background():
    source_found = False
    for layer in QgsProject.instance().mapLayers().values():
        if 'xyz&url' in layer.source():
            source_found = True
    if not source_found:
        url_with_params = 'type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0'
        rlayer = QgsRasterLayer(url_with_params, 'Google satellite', 'wms')
        rlayer.isValid()
        QgsProject.instance().addMapLayer(rlayer)


def histedges_equalN(x, nbin):
    """Nice function found at https://stackoverflow.com/questions/39418380/histogram-with-equal-number-of-points-in-each-bin"""
    npt = len(x)
    return np.interp(np.linspace(0, npt, nbin + 1),
                     np.arange(npt),
                     np.sort(x))


class CreateLayer:
    def __init__(self, db, dock_widget=None):
        """Creates a layer with color coded attributes"""
        self.db = db
        self.dock_widget = dock_widget

    def _apply_symbology_fixed_divisions(self, layer, field, tbl_name, schema,
                                         min_v, max_v, steps):
        """Finds the amount of levels that is necessary to describe the layer,
        a maximum of 20 different levels is set"""
        if min_v is not None and max_v is not None:
            distinct_values = list(np.arange(min_v, max_v, steps))
        else:
            distinct = self.db.get_distinct(tbl_name, field, schema)
            if len(distinct) == 1:
                return
            distinct_values = []
            distinct_count = []
            for value, count in distinct:
                distinct_values.append(value)
                distinct_count.append(count)
            if len(distinct_values) > 20:
                distinct_values.sort()
                temp_list = []
                for val in range(0, len(distinct_values), int(round(len(distinct_values)/20))):
                    temp_list.append(distinct_values[val])
                distinct_values = temp_list

        colors = self._create_colors(len(distinct_values))
        try:
            range_list = []
            for i in range(len(distinct_values) - 1):
                red, green, blue = colors[i]
                range_list.append(self._make_symbology(layer, distinct_values[i],
                                                     distinct_values[i + 1],
                                                     str(distinct_values[i]) + ' - ' + str(distinct_values[i + 1]),
                                                     QColor(int(red*255),int(green*255), int(blue*255), 128) ) )
            renderer = QgsGraduatedSymbolRenderer(field, range_list)
            renderer.setMode(QgsGraduatedSymbolRenderer.Custom )
        except TypeError:
            categories = []
            for i in range(len(distinct_values)):
                symbol = QgsSymbol.defaultSymbol(layer.geometryType())
                red, green, blue = colors[i]
                symbol.setColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                symbol.symbolLayer(0).setStrokeColor(QColor(int(red*255),int(green*255), int(blue*255), 128))
                category = QgsRendererCategory(str(distinct_values[i]), symbol, str(distinct_values[i]))
                categories.append(category)
            renderer = QgsCategorizedSymbolRenderer(field, categories)
            #renderer.setMode(QgsCategorizedSymbolRenderer.Custom)
        layer.setRenderer(renderer)

    def _make_symbology(self, layer, min , max, title, color):
        """Creates the symbols and sets the coloring of the layer"""
        symbol = self._validated_default_symbol(layer.geometryType() )
        symbol.setColor(color)
        symbol.symbolLayer(0).setStrokeColor(color)
        range = QgsRendererRange(min, max, symbol, title)
        return range

    def _create_colors(self, number_of_items):
        """Returning a list of lists with RGB code, where the size of the list
         is equals the number_of_items"""
        colors = []
        for i in range(number_of_items):
            value = float(i) / float(number_of_items)
            colors.append(rg(value))
        return colors

    def _validated_default_symbol(self, geometryType ):
        """Validates that the symbol is of the correct type, (point, line or
        polygon and then returning a Qgis type symbol)"""
        symbol = QgsSymbol.defaultSymbol( geometryType )
        if symbol is None:
            if geometryType == Qgis.Point:
                symbol = QgsMarkerSymbol()
            elif geometryType == Qgis.Line:
                symbol =  QgsLineSymbol()
            elif geometryType == Qgis.Polygon:
                symbol = QgsFillSymbol()
        return symbol

    def equal_count(self, layer, data_values_list, field, steps=10,
                    min_value=None, max_value=None):
        if min_value is not None:
            values = []
            for value in data_values_list:
                if value >= min_value:
                    values.append(value)
            data_values_list = values
        if max_value is not None:
            values = []
            for value in data_values_list:
                if value <= max_value:
                    values.append(value)
            data_values_list = values
        count_0 = data_values_list.count(0)
        if count_0 > 1:
            def remove_values_from_list(the_list, val):
                return [value for value in the_list if value != val]
            data_values_list = remove_values_from_list(data_values_list, 0)
            data_values_list.insert(0, 0)
        n, bins, patches = plt.hist(data_values_list,
                                    histedges_equalN(data_values_list, steps))
        colors = self._create_colors(steps)
        range_list = []
        for i in range(steps):
            red, green, blue = colors[i]
            range_list.append(
                self._make_symbology(layer, bins[i],
                                     bins[i + 1],
                                     str(bins[i]) + ' - ' + str(
                                         bins[i + 1]),
                                     QColor(int(red * 255),
                                            int(green * 255),
                                            int(blue * 255), 128)))
        renderer = QgsGraduatedSymbolRenderer(field, range_list)
        renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
        layer.setRenderer(renderer)
        return layer

    def create_layer_style(self, layer, target_field, tbl_name, schema, min=None, max=None, steps=None):
        """Create the layer and adds the layer to the canvas"""
        if layer.isValid():
            self._apply_symbology_fixed_divisions(layer, target_field, tbl_name, schema, min, max, steps)
            QgsProject.instance().addMapLayers([layer])

    def repaint_layer(self):
        cb = self.dock_widget.mMapLayerComboBox
        layer = cb.currentLayer()
        field = layer.renderer().classAttribute()
        min_user_val = float(self.dock_widget.LEMinColor.text())
        max_user_val = float(self.dock_widget.LEMaxColor.text())
        max_nbr_user_val = float(self.dock_widget.LEMaxNbrColor.text())
        v2_step = int((max_user_val - min_user_val) / max_nbr_user_val)
        self._apply_symbology_fixed_divisions(layer, field, None, None,
                                              min_user_val, max_user_val,
                                              v2_step)
        layer.triggerRepaint()