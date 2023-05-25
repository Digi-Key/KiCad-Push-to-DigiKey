import re
import pathlib


def get_sch_file_name(p: str):
    # `p`: pcb_path = board.GetFileName()
    _pcb_file_name = pathlib.Path(p).resolve().name
    if _pcb_file_name.lower().endswith('.kicad_pcb')\
            or _pcb_file_name.lower().endswith('.kicad_sch'):
        _sch_file_name = _pcb_file_name[:-10]
    else:
        _sch_file_name = 'From KiCad plugin'
    if len(_sch_file_name.strip()) == 0:
        return 'From KiCad plugin'
    return _sch_file_name


def pcb_2_sch_path(p: str):
    _parent_path = pathlib.Path(p).resolve().parent
    _pcb_file_name = pathlib.Path(p).resolve().name
    if _pcb_file_name.lower().endswith('.kicad_pcb'):
        _sch_file_name = _pcb_file_name[:-10] + '.kicad_sch'
    else:
        _sch_file_name = _pcb_file_name + '.kicad_sch'
    return _parent_path.joinpath(_sch_file_name)


def json_from_bom__with_pn_as_key(bom):
    # comply with: /mylists/api/thirdparty
    json_object = []
    for _pn in bom:
        _item = bom[_pn]
        json_object.append({
            "requestedPartNumber": _pn,
            "quantities": [
                {
                    "quantity": _item.get('qty', 0)
                }
            ],
            "customerReference": _item.get('cusRef', ''),
            "notes": _item.get('note', ''),
        })
    return json_object


def to_string(_list):
    if not isinstance(_list, list):
        return str(_list)
    return ','.join([str(_) for _ in _list if str(_).strip() != ''])


def parse_property_line(line: str):
    # KiCad 6.0
    # '    (property "Datasheet" "~" (id 3) (at 44.45 63.5 0)'
    # --> name: "Datasheet", value: "~"

    # KiCad 7.0
    # '    (property "Reference" "R2" (at 90.17 80.645 0)'
    # --> name: "Reference", value: "R2"
    property_line_regex = re.compile(r'^\s{4}\(property "(.*)" "(.*)"')
    if not property_line_regex.search(line):
        return
    _name, _value = property_line_regex.findall(line)[0]
    return {
        'name': _name,
        'value': _value,
    }


def parse_uuid(s: str):
    uuid_regex = re.compile(r'([A-Fa-f0-9]{8}'
                            r'-[A-Fa-f0-9]{4}'
                            r'-[A-Fa-f0-9]{4}'
                            r'-[A-Fa-f0-9]{4}'
                            r'-[A-Fa-f0-9]{12}'
                            r')')
    if not uuid_regex.search(s):
        return
    return uuid_regex.findall(s)[0]  # first matched


def get_symbol_dict(kicad_sch_path):
    # one traversal to improve performance: 18s -->0.07s
    # SAMPLE OUTPUT
    # {
    # '00000000-0000-0000-0000-00006319aa5a': [
    #   {'name': 'Reference', 'value': 'AU1', 'property_id': '0'},
    #   {'name': 'Value', 'value': '', 'property_id': '1'},
    #   {'name': 'Footprint', 'value': '', 'property_id': '2'},
    #   {'name': 'Datasheet', 'value': '', 'property_id': '3'},
    #   {'name': 'Name', 'value': '', 'property_id': '4'},
    #   {'name': 'Manufacturer', 'value': '', 'property_id': '5'},
    #   {'name': 'Manufacturer Part Number', 'value': '', 'property_id': '6'},
    #   {'name': 'Digikey Part Number', 'value': '', 'property_id': '7'}
    #  ],
    # '00000000-0000-0000-0000-00006319aa5b': [
    #   {'name': 'Reference', 'value': 'AU2', 'property_id': '0'},
    #   {'name': 'Value', 'value': '', 'property_id': '1'},
    #   ...
    #  ]
    # }
    symbols = {}
    new_symbol = False
    curr_uuid = None
    with open(kicad_sch_path, 'r', encoding='utf-8') as fi:
        lines = fi.readlines()
    for num, line in enumerate(lines):
        if '  (symbol (lib_id' in line:
            new_symbol = True
            curr_uuid = None
        if '    (uuid' in line and new_symbol:
            new_symbol = False
            curr_uuid = parse_uuid(line)
            symbols[curr_uuid] = []
        if '    (property ' in line and curr_uuid:
            symbol_property = parse_property_line(line)
            symbols[curr_uuid].append(symbol_property)
    return symbols


def score_field_name_as_part_number(field_name: str):
    score = 0
    # fname = field_name.lower()
    fname = ''.join([c.lower() for c in field_name if c.isalnum() or c.endswith('#')])
    if 'digi' in fname or 'dk' in fname:
        score += 50
    if 'number' in fname or 'pn' in fname:
        score += 30
    if 'part' in fname:
        score += 20
    if 'product' in fname or fname.endswith('#'):
        score += 10
    if 'value' in fname:  # Cody: sometimes I spotted PN was entered here
        score += 5
    # these fields are known not to be part number
    if fname in ['caution', 'datasheet', 'designnote', 'designator', 'designnotes',
                 'distributed', 'distributedby', 'distributor',
                 'environmentalinformation', 'environmentinfo',
                 'environmentinformation', 'footprint', 'installation', 'made',
                 'madeby', 'madein', 'make', 'maker', 'mfg', 'mfg.', 'mfr',
                 'mfr.', 'note', 'notes', 'package', 'packages', 'packaging',
                 'pin', 'pincount', 'pins', 'productpage', 'ref', 'refdes',
                 'reference', 'series', 'url', 'usage', 'use', 'warning', 'web',
                 'webpage', 'website', 'year']:
        score -= 20
    return score


def score_field_value_as_part_number(field_value: str):
    # PLUS
    # specific known regexes (60%)
    # lower/upper case (20%)
    # length (10%)
    # containing characters (10%)
    # -- not in dictionary (will not do, too difficult) --

    # MINUS
    # non-ASCII characters
    # known keywords

    score = 0
    # upper/lower case
    # part number is more likely written in upper case
    if field_value.isupper():
        score += 20
    fv = field_value.upper()

    # known allowed characters
    # may contain:
    #   - /, -, #, _, comma, dot, space
    #   - +, (, ), =, &, \, _, *, ;, ", ', %, [, ]
    char_and_length_regex = re.compile(r'^[A-Z0-9#+()/\-\s,.=&:\\_*;"\'%\[\]]{1,49}$')
    if char_and_length_regex.match(field_value):
        score += 10
    # penalty if not ASCII
    if not fv.isascii():
        score -= 20

    # length
    # average length in range (decrease in quantity):
    # - [11, 24]
    # - [10], [25, 31]
    # - [8, 9], [32, 37]
    # - the rest
    if len(fv) in range(11, 25):
        score += 10
    elif len(fv) in range(10, 11) or len(fv) in range(25, 32):
        score += 5
    elif len(fv) in range(8, 10) or len(fv) in range(32, 38):
        score += 2

    # known regexes
    # Digi-Key packaging:
    #   - Tape & Reel (TR): TR-ND, -2-ND
    #   - Cut Tape (CT): CT-ND, -1-ND
    #   - Digi-Reel (DKR): DKR-ND, -6-ND
    if fv.endswith('-ND'):
        score += 50
    if fv.endswith('TR-ND') or fv.endswith('-2-ND') \
            or fv.endswith('CT-ND') or fv.endswith('-1-ND') \
            or fv.endswith('DKR-ND') or fv.endswith('-6-ND'):
        score += 10
    categorized_regex = re.compile(r'^\d{1,4}-.*-ND$')
    if categorized_regex.match(fv):
        score += 10
    return score


def parse_fields(symbol_dict: dict):
    # `id` is no longer a reliable for the identifier of a property,
    # now use `name` instead. Beware: it's case-sensitive.

    # SAMPLE OUTPUT (`name` redundancy is intended):
    # {
    # 'Reference': {'name': 'Reference'},
    # 'Value': {'name': 'Value'},
    # 'Footprint': {'name': 'Footprint'},
    # 'Datasheet': {'name': 'Datasheet'},
    # 'Name': {'name': 'Name'},
    # 'Manufacturer': {'name': 'Manufacturer'},
    # 'Manufacturer Part Number': {'name': 'Manufacturer Part Number'},
    # 'Digikey Part Number': {'name': 'Digikey Part Number},
    # }
    fields = {}  # name (as str): {name, scores}
    for _k, _v_symbol in symbol_dict.items():  # every symbol
        for _prop in _v_symbol:  # every field in symbol
            if _prop['name'] not in fields:
                fields[_prop['name']] = {
                    'name': _prop['name']
                }
    return fields


def score_fields_as_part_number(symbol_dict: dict):
    # SAMPLE OUTPUT:
    # {
    # 'Reference': {'name': 'Reference', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Value': {'name': 'Value', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Footprint': {'name': 'Footprint', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Datasheet': {'name': 'Datasheet', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Name': {'name': 'Name', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Manufacturer': {'name': 'Manufacturer', 'name_score': 0, 'values_score': 120, 'field_score': 0},
    # 'Manufacturer Part Number': {'name': 'Manufacturer Part Number', 'name_score': 50, 'values_score': 360, 'field_score': 18_000},
    # 'Digikey Part Number': {'name': 'Digikey Part Number', 'name_score': 60, 'values_score': 480, 'field_score': 28_800}
    # }
    fields_with_score = parse_fields(symbol_dict)
    for fname in fields_with_score:
        fname_score = score_field_name_as_part_number(fname)
        fvalues_score = 0
        for symbol_properties in symbol_dict.values():
            for symbol_property in symbol_properties:
                if symbol_property['name'] == fname:
                    fvalue = symbol_property['value']
                    fvalues_score += score_field_value_as_part_number(fvalue)
        fields_with_score[fname]['name_score'] = fname_score
        fields_with_score[fname]['values_score'] = fvalues_score
        fields_with_score[fname]['field_score'] = fname_score * fvalues_score
    return fields_with_score


# get symbol list
# get fields (headers only)
# choose the field with the highest Part Number score
# if 2 or more fields have score above a threshold
#   init sum_score = 0 for each above field
#   for every row
#       compute score for those fields
#       add to the corresponding sum
# choose the field with the highest sum score
# if 2 or more fields have the highest sum score
#   pick the field with higher id
# if user picks a column manually (they don't have to), honor user's choice
def auto_select_part_number_field(symbol_dict):
    # SAMPLE OUTPUT:
    # {'name': 'DK_PN', 'name_score': 80, 'values_score': 1310, 'field_score': 104_800}
    field_scores = score_fields_as_part_number(symbol_dict)
    _first_field = list(field_scores.keys())[0]
    _hi_score = field_scores[_first_field]['field_score']
    _hi_fname = field_scores[_first_field]['name']
    for fname in field_scores:
        if field_scores[fname]['name_score'] >= 0:
            if field_scores[fname]['field_score'] > _hi_score:
                _hi_score = field_scores[fname]['field_score']
                _hi_fname = field_scores[fname]['name']
    return field_scores[_hi_fname]
    # only fields with name_score >= threshold are considered
    # pick the last highest field_score
    # if all fields have name_score < threshold, pick the last field with the highest score


def make_quantity(symbol_dict: dict, pn_field_str: str):
    # input: symbol_dict with uuid as key
    # output: symbol_dict with part number as key (symbol_dict_by_pn),
    #         with new column: quantity
    symbol_dict_by_pn = {}
    for k_symbol_uuid, v_symbol_properties in symbol_dict.items():
        symbol_key = None
        for symbol_property in v_symbol_properties:
            if symbol_property['name'] == pn_field_str:
                symbol_key = symbol_property['value']
        if not symbol_key:  # ignore None or '' values
            continue
        if symbol_key not in symbol_dict_by_pn:  # add new
            symbol_dict_by_pn[symbol_key] = {}
            symbol_dict_by_pn[symbol_key]['symbol_uuids'] = [k_symbol_uuid]
            symbol_dict_by_pn[symbol_key]['quantity'] = 1
            for symbol_property in v_symbol_properties:
                property_name = symbol_property['name']
                property_value = symbol_property['value']
                if property_name != pn_field_str:
                    symbol_dict_by_pn[symbol_key][property_name] = {}
                    symbol_dict_by_pn[symbol_key][property_name]['name'] = property_name  # singular
                    symbol_dict_by_pn[symbol_key][property_name]['values'] = [property_value]  # plural
        else:  # append values to an existing
            symbol_dict_by_pn[symbol_key]['symbol_uuids'].append(k_symbol_uuid)
            symbol_dict_by_pn[symbol_key]['quantity'] += 1
            for symbol_property in v_symbol_properties:
                property_name = symbol_property['name']
                property_value = symbol_property['value']
                # print(symbol_key, property_name, property_value)
                if property_name != pn_field_str:
                    if property_name in symbol_dict_by_pn[symbol_key]:
                        symbol_dict_by_pn[symbol_key][property_name]['values'].append(property_value)
                    else:
                        symbol_dict_by_pn[symbol_key][property_name] = {}
                        symbol_dict_by_pn[symbol_key][property_name]['name'] = property_name
                        symbol_dict_by_pn[symbol_key][property_name]['values'] = [property_value]
    return symbol_dict_by_pn
