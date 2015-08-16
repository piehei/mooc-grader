from django import forms
from access.config import ConfigError
from django.forms.widgets import CheckboxSelectMultiple, RadioSelect, Textarea
from django.utils.safestring import mark_safe
from util.templates import template_to_str
import re

class GradedForm(forms.Form):
    '''
    A dynamically build form class for an exercise.

    '''

    def __init__(self, *args, **kwargs):
        '''
        Constructor. Requires keyword argument "exercise".

        '''
        if "exercise" not in kwargs:
            raise ConfigError("Missing exercise configuration from form arguments.")
        self.exercise = kwargs.pop("exercise")
        super(forms.Form, self).__init__(*args, **kwargs)
        if "fieldgroups" not in self.exercise:
            raise ConfigError("Missing required \"fieldgroups\" in exercise configuration")

        g = 0
        i = 0

        # Travel each fields froup.
        for group in self.exercise["fieldgroups"]:
            if "fields" not in group:
                raise ConfigError("Missing required \"fields\" in field group configuration")
            j = 0
            l = len(group["fields"]) - 1

            # Travel each field in group.
            for field in group["fields"]:
                if "type" not in field:
                    raise ConfigError("Missing required \"type\" in field configuration for: %s" % (group["name"]))
                t = field["type"]

                # Create a field by type.
                f = None
                r = "required" in field and field["required"]
                atr = {"class": "form-control"}
                if t == "checkbox":
                    f = forms.MultipleChoiceField(widget=forms.CheckboxSelectMultiple(),
                        required=r, choices=self.create_choices(field))
                elif t == "radio":
                    f = forms.ChoiceField(widget=forms.RadioSelect(), required=r,
                        choices=self.create_choices(field))
                elif t == 'dropdown':
                    f = forms.ChoiceField(widget=forms.Select(attrs=atr), required=r,
                        choices=self.create_choices(field))
                elif t == "text":
                    f = forms.CharField(widget=forms.TextInput(attrs=atr), required=r)
                elif t == "textarea":
                    f = forms.CharField(widget=forms.Textarea(attrs=atr), required=r)
                else:
                    raise ConfigError("Unknown field type: %s" % (t))
                f.type = t
                f.choice_list = (t == "checkbox" or t == "radio")

                # Set field defaults.
                f.label = mark_safe(field["title"])
                f.more = self.create_more(field)
                if j == 0:
                    f.open_set = self.group_name(g)
                    if "title" in group:
                        f.set_title = group["title"]
                elif j >= l:
                    f.close_set = True
                j += 1

                # Store field in form.
                self.fields[self.field_name(i)] = f
                i += 1
            g += 1


    def create_more(self, configuration):
        '''
        Creates more instructions by configuration.

        '''
        more = ""
        if "more" in configuration:
            more += configuration["more"]
        if "include" in configuration:
            more += template_to_str(None, None, configuration["include"])
        return more or None


    def create_choices(self, configuration):
        '''
        Creates field choices by configuration.

        '''
        choices = []
        if "options" in configuration:
            i = 0
            for opt in configuration["options"]:
                label = ""
                if "label" in opt:
                    label = opt["label"]
                choices.append((self.option_name(i), mark_safe(label)))
                i += 1
        return choices


    def group_name(self, i):
        return "group_%d" % (i)


    def field_name(self, i):
        return "field_%d" % (i)


    def option_name(self, i):
        return "option_%d" % (i)


    def grade(self):
        '''
        Grades form answers.

        '''
        points = 0
        error_fields = []
        error_groups = []
        g = 0
        i = 0
        for group in self.exercise["fieldgroups"]:
            for field in group["fields"]:
                name = self.field_name(i)
                val = self.cleaned_data.get(name, None)
                if self.grade_field(field, val):
                    if "points" in field:
                        points += field["points"]
                else:
                    error_fields.append(name)
                    gname = self.group_name(g)
                    if gname not in error_groups:
                        error_groups.append(gname)
                i += 1
            g += 1
        return (points, error_groups, error_fields)


    def grade_field(self, configuration, value):
        '''
        Grades field answer.

        '''
        t = configuration["type"]

        # Grade checkbox: all correct required if any configured
        if t == "checkbox":
            i = 0
            correct_exists = False
            incorrect = False
            for opt in configuration["options"]:
                name = self.option_name(i)
                if "correct" in opt and opt["correct"]:
                    correct_exists = True
                    if name not in value:
                        return False
                elif name in value:
                    incorrect = True
                i += 1
            return not correct_exists or not incorrect

        # Grade radio: correct required if any configured
        elif t == "radio" or t == "dropdown":
            i = 0
            correct_exists = False
            for opt in configuration["options"]:
                name = self.option_name(i)
                if "correct" in opt and opt["correct"]:
                    correct_exists = True
                    if name == value:
                        return True
                i += 1
            return not correct_exists

        # Grade text: correct text required if configured
        elif t == "text" or t == "textarea":
            if "correct" in configuration:
                return value.strip() == configuration["correct"]
            elif "regex" in configuration:
                p = re.compile(configuration["regex"])
                return p.match(value.strip()) != None
            return True

        raise ConfigError("Unknown field type for grading: %s" % (configuration["type"]))
