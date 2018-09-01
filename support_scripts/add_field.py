from qgis.core import QgsProject, QgsVectorLayer, QgsRasterLayer, QgsRectangle, QgsCoordinateReferenceSystem, \
    QgsMapSettings
from PyQt5 import QtCore
from PyQt5.QtWidgets import QMessageBox, QListWidgetItem, QApplication
from operator import xor
from psycopg2 import ProgrammingError, IntegrityError, InternalError
from ..widgets.add_field import AddFieldFileDialog
#import pydevd
#pydevd.settrace('localhost', port=53100, stdoutToServer=True, stderrToServer=True)


class AddField:
    def __init__(self, parent_widget):
        """This class creates a guide file
        :param parent_widget"""
        self.iface = parent_widget.iface
        self.db = parent_widget.db
        self.tr = parent_widget.tr
        self.dock_widget = parent_widget.dock_widget
        self.parent = parent_widget
        self.AFD = AddFieldFileDialog()
        self._enable_years()
        self.field = None

    def _enable_years(self):
        for nr, y in enumerate(range(2000, 2030)):
            self.AFD.CBYear.addItem(str(y))
            item = self.AFD.CBYear.model().item(nr, 0)
            item.setCheckState(QtCore.Qt.Checked)
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsEditable))
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsUserCheckable))
            item.setFlags(xor(item.flags(), QtCore.Qt.ItemIsSelectable))

    def run(self):
        """Presents the sub widget HandleInput and connects the different
        buttons to their function"""
        self.AFD.show()
        self.AFD.PBSelectExtent.clicked.connect(self.clicked_define_field)
        self.AFD.PBSave.clicked.connect(self.save)
        self.AFD.PBHelp.clicked.connect(self.help)
        self.AFD.PBQuit.clicked.connect(self.quit)
        self.AFD.exec()
        self.parent.populate.reload_fields()

    def set_widget_connections(self):
        self.parent.dock_widget.PBAddField.clicked.connect(self.run)
        self.parent.dock_widget.PBRemoveField.clicked.connect(self.remove_field)
        self.parent.dock_widget.PBViewFields.clicked.connect(self.view_fields)

    def remove_field(self):
        """Removes a field that the user wants, a check that there are no
        data that is depended on is made."""
        for i in range(self.parent.dock_widget.LWFields.count()):
            item = self.parent.dock_widget.LWFields.item(i)
            if item.checkState() == 2:
                field_name = item.text()
                qm = QMessageBox()
                res = qm.question(None, self.tr('Question'),
                                  self.tr("Do you want to delete ") + str(field_name),
                                  qm.Yes, qm.No)
                if res == qm.No:
                    continue
                # TODO: Check more than planting manuel
                planting = self.db.execute_and_return("select field_name from plant.manual")
                stop_removing = False
                for row in planting:
                    if row[0] == field_name:
                        QMessageBox.information(None, self.tr('Error'),
                                                self.tr('There are planting data that are dependent on this field, '
                                                        'it cant be removed.'))
                        stop_removing = True
                if stop_removing:
                    continue
                sql = "delete from fields where field_name='{f}'".format(f=field_name)
                self.db.execute_sql(sql)
                self.parent.dock_widget.LWFields.takeItem(i)

    def view_fields(self):
        """Add all fields that aren't displayed on the canvas, if no background map is loaded Google maps are loaded."""
        sources = [layer.source() for layer in QgsProject.instance().mapLayers().values()]
        source_found = False
        zoom_extent = QgsRectangle()
        for layer in QgsProject.instance().mapLayers().values():
            if 'xyz&url' in layer.source():
                source_found = True
            else:
                zoom_extent.combineExtentWith(layer.extent())
        if not source_found:
            url_with_params = 'type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0'
            rlayer = QgsRasterLayer(url_with_params, 'Google satellite', 'wms')
            rlayer.isValid()
            QgsProject.instance().addMapLayer(rlayer)
        fields_db = self.db.execute_and_return("select field_name from fields")
        for field in fields_db:
            field = field[0]
            found = False
            for source in sources:
                if str(field).lower() in source.lower():
                    found = True
            if found:
                continue
            layer = self.db.addPostGISLayer('fields', 'polygon', 'public',
                                            extra_name=field + '_',
                                            filter_text="field_name='{f}'".format(f=field))
            QgsProject.instance().addMapLayer(layer)
        for layer in QgsProject.instance().mapLayers().values():
            if 'xyz&url' not in layer.source():
                zoom_extent.combineExtentWith(layer.extent())
        print(zoom_extent.center().x())
        if zoom_extent.center().x() != 0.0:
            wgsCRS = QgsCoordinateReferenceSystem(4326)
            QgsProject.instance().setCrs(wgsCRS)
            zoom_extent.scale(1.1)  # Increase a bit the extent to make sure all geometries lie inside
            self.parent.iface.mapCanvas().setExtent(zoom_extent)
            self.parent.iface.mapCanvas().refresh()
            wgsCRS = QgsCoordinateReferenceSystem(3857)
            QgsProject.instance().setCrs(wgsCRS)

    def clicked_define_field(self):
        """Creates an empty polygon that's define a field"""
        name = self.AFD.LEFieldName.text()
        if len(name) == 0:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name must be filled in.'))
            return
        self.field = QgsVectorLayer("Polygon?crs=epsg:4326", name, "memory")
        source_found = False
        zoom_extent = QgsRectangle()
        for layer in QgsProject.instance().mapLayers().values():
            if 'xyz&url' in layer.source():
                source_found = True
            else:
                zoom_extent.combineExtentWith(layer.extent())
        if not source_found:
            url_with_params = 'type=xyz&url=https://mt1.google.com/vt/lyrs%3Ds%26x%3D%7Bx%7D%26y%3D%7By%7D%26z%3D%7Bz%7D&zmax=19&zmin=0'
            rlayer = QgsRasterLayer(url_with_params, 'Google satellite', 'wms')
            rlayer.isValid()
            QgsProject.instance().addMapLayer(rlayer)
        self.field.startEditing()
        self.iface.actionAddFeature().trigger()
        QgsProject.instance().addMapLayer(self.field)
        if zoom_extent.center().x() != 0.0:
            wgsCRS = QgsCoordinateReferenceSystem(4326)
            QgsProject.instance().setCrs(wgsCRS)
            zoom_extent.scale(2)
            self.parent.iface.mapCanvas().setExtent(zoom_extent)
            self.parent.iface.mapCanvas().refresh()
            wgsCRS = QgsCoordinateReferenceSystem(3857)
            QgsProject.instance().setCrs(wgsCRS)

    def quit(self):
        """Closes the widget."""
        self.AFD.done(0)

    def save(self):
        """Saves the field in the database"""
        try:
            self.iface.actionSaveActiveLayerEdits().trigger()
            self.iface.actionToggleEditing().trigger()
            feature = self.field.getFeature(1)
        except:
            QMessageBox.information(None, self.tr("Error:"), self.tr(
                'No coordinates where found, did you mark the field on the canvas?'))
            return
        polygon = feature.geometry().asWkt()
        name = self.AFD.LEFieldName.text()
        if len(name) == 0:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name must be filled in.'))
            return
        year_str = ''
        for nr, y in enumerate(range(2000, 2030)):
            item = self.AFD.CBYear.model().item(nr, 0)
            if item.checkState():
                year_str += str(y) + ','
        year_str =year_str[:-1]
        sql = """Insert into fields (field_name, years, polygon) 
        VALUES ('{name}', '{year}', st_geomfromtext('{poly}', 4326))""".format(name=name, year=year_str, poly=polygon)
        try:
            self.db.execute_sql(sql)
        except IntegrityError:
            QMessageBox.information(None, self.tr('Error:'),
                                    self.tr('Field name all ready exist, please select a new name'))
            return
        except InternalError as e:
            QMessageBox.information(None, self.tr('Error:'),
                                    str(e))
            return
        _name = QApplication.translate("qadashboard", name, None)
        item = QListWidgetItem(_name, self.dock_widget.LWFields)
        item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
        item.setCheckState(QtCore.Qt.Unchecked)

    def help(self):
        QMessageBox.information(None, self.tr("Help:"), self.tr(
            'Here is where you add a field.\n'
            '1. Start with giving the field a name.\n'
            '2. Press "select extent" and switch to the QGIS window and zoom to your field.\n'
            '3. To mark your field, left click with the mouse in one corner of the field.\n'
            'then left click in all corners of the field then right click anywhere on the map.\n'
            '(There might be some errors while clicking the corners if the lines are crossing each other but in the end this does not matter if they does not do it in the end)\n'
            '4. If a field is temporary or only valid since/until you can specify which years the field is valid to.\n'
            '5. Press "Save field" to store the field.\n'
            '6. When all fields are added press "Finished"'))
        return
