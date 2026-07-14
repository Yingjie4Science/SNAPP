/****
 * National per-county Landsat NDVI (Google Earth Engine Code Editor)
 *
 * Faster batch-export replacement for ndvi_gee_national.py.  Run this script
 * in https://code.earthengine.google.com after uploading the project county
 * AOI layer (data/national/counties.gpkg) as an Earth Engine FeatureCollection.
 *
 * METHOD (matched to ndvi_gee_national.py / ndvi_gee.py)
 *   - Landsat Collection 2, Tier 1, Level 2 surface reflectance (L5/7/8/9)
 *   - June-September (JJAS), annual 90th-percentile NDVI
 *   - C2 scale/offset applied before NDVI
 *   - QA_PIXEL bits 0-4 clear; QA_RADSAT clear for Landsat 8/9
 *   - L7 restricted to 2012 because of SLC-off striping
 *   - 30 m GeoTIFFs in CONUS Albers (EPSG:5070), one per county
 *
 * BEFORE RUNNING
 *   1. Create the project AOI locally:
 *        python src/national/build_metro_counties.py --crosswalk
 *   2. Upload data/national/counties.gpkg to Earth Engine as a table asset.
 *      Preserve GEOID as text, including leading zeros. STATEFP and COUNTYFP
 *      are also supported and are used to construct a reliable five-digit ID.
 *   3. Replace COUNTIES_ASSET below with the resulting asset ID.
 *   4. Choose YEAR and an index batch. Tasks appear in the Tasks tab; click
 *      Run All. Keep each batch below the Earth Engine ready-task limit.
 *   5. Download Drive outputs into data/national/ndvi/ without renaming them,
 *      then run: bash run_national.sh data/national/counties.gpkg data/national/ndvi
 *
 * Exports are intentionally one county per task: this keeps each raster
 * compatible with the existing national runner and avoids giant CONUS exports.
 ****/

// --------------------------- USER SETTINGS ---------------------------------

// REQUIRED: asset uploaded from data/national/counties.gpkg.
var COUNTIES_ASSET = 'projects/YOUR_EE_PROJECT/assets/snapp_national_counties';

var YEAR = 2024;
var DRIVE_FOLDER = 'ndvi_national';
var START_INDEX = 0;       // Zero-based index in GEOID-sorted counties.
var EXPORT_COUNT = 100;    // Reduce if your Tasks tab is near its ready-task limit.
var OUTPUT_CRS = 'EPSG:5070';
var SCALE_METERS = 30;
var PREVIEW_GEOID = null;  // e.g. '06075', or null to skip a map preview.

// ---------------------------------------------------------------------------

var SEASON = ee.Filter.calendarRange(6, 9, 'month');
var YEAR_START = ee.Date.fromYMD(YEAR, 1, 1);
var YEAR_END = YEAR_START.advance(1, 'year');

/** Apply Landsat Collection 2 Level-2 reflectance scaling. */
function applyScaleFactors(image) {
  var optical = image.select('SR_B.').multiply(0.0000275).add(-0.2);
  var thermal = image.select('ST_B.*').multiply(0.00341802).add(149.0);
  return image.addBands(optical, null, true).addBands(thermal, null, true);
}

/** Keep only pixels with QA_PIXEL bits 0--4 clear (fill/cloud/shadow etc.). */
function clearQaMask(image) {
  return image.select('QA_PIXEL').bitwiseAnd(parseInt('11111', 2)).eq(0);
}

function maskL457(image) {
  return image.updateMask(clearQaMask(image));
}

function maskL89(image) {
  return image.updateMask(clearQaMask(image))
      .updateMask(image.select('QA_RADSAT').eq(0))
      .select('SR_B[0-9]*')
      .copyProperties(image, ['system:time_start']);
}

function addNdviL57(image) {
  return image.addBands(image.normalizedDifference(['SR_B4', 'SR_B3']).rename('NDVI'));
}

function addNdviL89(image) {
  return image.addBands(image.normalizedDifference(['SR_B5', 'SR_B4']).rename('NDVI'));
}

/** Filter, scale, mask, and calculate NDVI for one sensor and one county. */
function prepare(collectionId, geometry, maskFn, ndviFn, start, end) {
  return ee.ImageCollection(collectionId)
      .filterDate(start, end)
      .filter(SEASON)
      .filterBounds(geometry)
      .map(applyScaleFactors)
      .map(maskFn)
      .map(ndviFn)
      .select('NDVI');
}

/**
 * Annual JJAS p90 NDVI for a county.  Restricting the source collections to
 * YEAR before compositing is equivalent to the Python lazy GEE graph but makes
 * the intended computation explicit and avoids unnecessary collection scans.
 */
function yearlyP90(geometry) {
  var l5 = prepare('LANDSAT/LT05/C02/T1_L2', geometry, maskL457, addNdviL57,
      YEAR_START, YEAR_END);
  var l8 = prepare('LANDSAT/LC08/C02/T1_L2', geometry, maskL89, addNdviL89,
      YEAR_START, YEAR_END);
  var l9 = prepare('LANDSAT/LC09/C02/T1_L2', geometry, maskL89, addNdviL89,
      YEAR_START, YEAR_END);

  // Match the Python rule: use L7 only in the 2012 SLC-off transition window.
  var l7 = ee.ImageCollection([]);
  if (YEAR === 2012) {
    l7 = prepare('LANDSAT/LE07/C02/T1_L2', geometry, maskL457, addNdviL57,
        ee.Date('2012-04-01'), ee.Date('2013-04-01'));
  }

  return l5.merge(l7).merge(l8).merge(l9)
      .reduce(ee.Reducer.percentile([90]))
      .rename('NDVI')
      .clip(geometry)
      .set({'year': YEAR, 'composite': 'JJAS Landsat C2 p90 NDVI'});
}

/**
 * Standardize the county export ID. The STATEFP+COUNTYFP route protects
 * against a table upload that accidentally turns GEOID 06075 into numeric 6075.
 */
function withExportGeoid(feature) {
  var props = feature.propertyNames();
  var hasParts = props.contains('STATEFP').and(props.contains('COUNTYFP'));
  var idFromParts = ee.String(feature.get('STATEFP')).cat(ee.String(feature.get('COUNTYFP')));
  var id = ee.String(ee.Algorithms.If(hasParts, idFromParts, feature.get('GEOID')));
  return feature.set('GEOID_EXPORT', id);
}

var counties = ee.FeatureCollection(COUNTIES_ASSET)
    .map(withExportGeoid)
    .sort('GEOID_EXPORT');

print('Counties in uploaded AOI', counties.size());
print('First counties', counties.limit(5));

// A bounded client-side batch is required: Export.image.toDrive creates tasks
// client-side and therefore cannot be called inside FeatureCollection.map().
var batch = counties.toList(EXPORT_COUNT, START_INDEX);
batch.evaluate(function(features) {
  if (!features || !features.length) {
    print('No counties in this batch. Check START_INDEX / EXPORT_COUNT.');
    return;
  }
  print('Creating ' + features.length + ' Drive tasks for year ' + YEAR +
      ' (sorted indices ' + START_INDEX + '–' + (START_INDEX + features.length - 1) + ').');
  features.forEach(function(raw) {
    var county = ee.Feature(raw);
    var geoid = String(raw.properties.GEOID_EXPORT);
    var geometry = county.geometry();
    var prefix = geoid + '_ndvi';  // required by run_national.sh / run_city.py
    Export.image.toDrive({
      image: yearlyP90(geometry),
      description: 'NDVI_p90_' + YEAR + '_' + geoid,
      folder: DRIVE_FOLDER,
      fileNamePrefix: prefix,
      region: geometry,
      scale: SCALE_METERS,
      crs: OUTPUT_CRS,
      maxPixels: 1e13,
      fileFormat: 'GeoTIFF',
      formatOptions: {noData: -9999.0},
      skipEmptyTiles: true
    });
  });
  print('Tasks created. Use the Tasks tab → Run All, then repeat with START_INDEX += EXPORT_COUNT.');
});

if (PREVIEW_GEOID !== null) {
  var preview = counties.filter(ee.Filter.eq('GEOID_EXPORT', String(PREVIEW_GEOID))).first();
  Map.centerObject(preview, 8);
  Map.addLayer(yearlyP90(preview.geometry()), {min: 0, max: 0.85, palette: ['beige', 'green']},
      'JJAS p90 NDVI ' + PREVIEW_GEOID);
  Map.addLayer(preview, {color: 'black'}, 'Preview county boundary');
}
