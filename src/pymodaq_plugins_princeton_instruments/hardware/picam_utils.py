def normalise_name(name):
    """Function to export standard names compatible with pyqtgraph conventions from the parameter names.
    Can be modified later if the naming convention changes."""
    return name.replace(' ', '_').lower()


def get_ROI_dictlist(ROI):
    """Return the dictionary for picam ROIs from the special type of parameter used in pylablib and picam for ROIs"""
    RDL = []
    for k in ROI._fields:
        RDL.append({'title': k, 'name': k, 'type': 'int', 'value': getattr(ROI, k)})
    return RDL

def define_pymodaq_pyqt_parameter(parameter):
    """Gets a parameter object from the pylablib module and initialise a dictionary compatible with pyqtgraph.
    Useful for getting automatically the parameters available for a camera.
    """
    # Get basic parameter attributes
    p_title = parameter.name
    p_fmt_name = normalise_name(parameter.name)
    p_type = None  # Here I just define p_type because it's going to be used later
    p_value = parameter.get_value(enum_as_str=True)
    p_limits = None
    p_readonly = not parameter.writable

    # Here it gets slightly intricate.
    # The parameters might be int,large int or float with a fixed number of
    # allowed values, in which case it is dealt as a list with some allowed values
    if parameter.kind in ['Integer', 'Large Integer']:
        # We recognize them because they have labels defined, i.e. the label dict is non-empty
        if parameter.labels != {}:
            p_type = 'list'
            p_limits = list(parameter.labels.values())
        else:
            p_type = 'int'
            # There might be limits though
            if parameter.cons_type == "Range" and parameter.cons_permanent is True:
                p_limits = [parameter.min, parameter.max]
            else:
                p_limits = None
    # The story is similar for floats
    elif parameter.kind == 'Floating Point':
        # We recognize them because they have labels defined, i.e. the label dict is non-empty
        if parameter.labels != {}:
            p_type = 'list'
            p_limits = list(parameter.labels.values())
        else:
            p_type = 'float'
            # There might be limits though
            if parameter.cons_type == "Range" and parameter.cons_permanent is True:
                p_limits = [parameter.min, parameter.max]
            else:
                p_limits = None
    # Boolean is easy
    elif parameter.kind == 'Boolean':
        p_type = 'bool'
    # Enumeration is ok
    elif parameter.kind == 'Enumeration':
        p_type = 'list'
        p_limits = list(parameter.labels.keys())  # Always str
    # ROIs are special
    elif parameter.kind == 'ROIs':
        p_type = 'group'
        # p_value = [get_ROI_dictlist(ROI) for ROI in parameter.get_value()]
        p_children = get_ROI_dictlist(parameter.get_value()[0])

        p_dict = {'title': p_title,
                  'name': p_fmt_name,
                  'type': p_type,
                  'children': p_children,
                  'readonly': p_readonly}

        return p_dict
    else:
        raise ValueError

    p_dict = {'title': p_title,
              'name': p_fmt_name,
              'type': p_type,
              'value': p_value,
              'readonly': p_readonly}

    if p_limits is not None:
        p_dict.update({'limits': p_limits})

    return p_dict

def sort_by_priority_list(values, priority):
    """
    Sorts a list of parameter dictionaries by a list of priority. Useful when setting up
    parameters automatically.
    """

    # priority_dict = {k: i for i, k in enumerate(priority)}

    # try to get a value from priority_dict using priority_dict.get(value).
    # If not found we just return the length of the list.
    # def priority_getter(value):
    #     return priority_dict.get(value['title'], len(values))
    def get_priority(value):
        try:
            return priority.index(value['title']) + 1
        except ValueError:
            return len(values)

    return sorted(values, key=get_priority)

def remove_settings_from_list(values, remove_list):
    """
    Remove settings belonging to the list.
    """
    return [val for val in values if val['title'] not in remove_list]
