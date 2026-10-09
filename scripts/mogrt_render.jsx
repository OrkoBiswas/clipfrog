var payload = __MOGRT_PAYLOAD__;
var inputFile = new File(payload.input_project);
var outputFile = new File(payload.output_project);
var statusFile = new File(payload.status_file);
function writeStatus(message) {
  statusFile.open("w");
  statusFile.write(message);
  statusFile.close();
}
app.beginSuppressDialogs();
writeStatus("opening project");
var project = app.open(inputFile);
writeStatus("project opened");
var exportComp = null;

for (var itemIndex = 1; itemIndex <= project.numItems; itemIndex++) {
  var item = project.item(itemIndex);
  if (item instanceof CompItem && item.name === payload.export_comp) {
    exportComp = item;
    break;
  }
}
if (!exportComp) throw new Error("MOGRT export composition was not found");

var master = project.items.addComp(
  "ClipForge MOGRT Sequence",
  payload.width,
  payload.height,
  1,
  payload.duration,
  30
);

function colorValue(value) {
  return [
    parseInt(value.substring(1, 3), 16) / 255,
    parseInt(value.substring(3, 5), 16) / 255,
    parseInt(value.substring(5, 7), 16) / 255,
    1,
  ];
}

function setColorControl(layer, name, color) {
  var effects = layer.property("ADBE Effect Parade");
  if (!effects) return;
  var effect = effects.property(name);
  if (effect) effect.property("ADBE Color Control-0001").setValue(colorValue(color));
}

function cloneTree(comp, suffix, text, depth) {
  if (depth > 12) throw new Error("MOGRT composition nesting is too deep");
  var duplicate = comp.duplicate();
  duplicate.name = comp.name + suffix;
  for (var layerIndex = 1; layerIndex <= duplicate.numLayers; layerIndex++) {
    var layer = duplicate.layer(layerIndex);
    if (layer.name === "Color Control") {
      setColorControl(layer, "Text", payload.primary_color);
      setColorControl(layer, "Text Animation", payload.effect_color);
      setColorControl(layer, "Shadow", payload.shadow_color);
      var effects = layer.property("ADBE Effect Parade");
      if (effects) {
        var opacity = effects.property("Shadow Opacity");
        if (opacity) {
          opacity.property("ADBE Slider Control-0001").setValue(payload.shadow_opacity * 100);
        }
      }
    }
    var textProperties = layer.property("ADBE Text Properties");
    if (textProperties) {
      var sourceText = textProperties.property("ADBE Text Document");
      if (sourceText) {
        var document = sourceText.value;
        document.text = text;
        document.font = payload.weight === 400 ? "Urbanist-Regular" : "Urbanist-Bold";
        sourceText.setValue(document);
      }
    }
    if (layer.source instanceof CompItem) {
      var child = cloneTree(layer.source, suffix, text, depth + 1);
      layer.replaceSource(child, false);
    }
  }
  return duplicate;
}

for (var cueIndex = 0; cueIndex < payload.cues.length; cueIndex++) {
  var cue = payload.cues[cueIndex];
  if (cue.end <= cue.start) continue;
  var cueComp = cloneTree(exportComp, " Cue " + cueIndex, cue.text, 0);
  var layer = master.layers.add(cueComp);
  var baseScale = (payload.width / 3840) * (payload.size / 42) * 100;
  layer.transform.scale.setValue([baseScale, baseScale]);
  layer.transform.position.setValue([
    payload.width * cue.x,
    payload.height * cue.y,
  ]);
  layer.startTime = cue.start;
  layer.inPoint = cue.start;
  layer.outPoint = Math.min(cue.end, payload.duration);
}

writeStatus("saving project");
project.save(outputFile);
project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
app.endSuppressDialogs(false);
writeStatus("complete");