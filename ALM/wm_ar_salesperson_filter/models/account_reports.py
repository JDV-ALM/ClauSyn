# -*- coding: utf-8 -*-
# Part of Waleed Mohsen. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
from odoo import models, fields, api, _
from odoo.exceptions import UserError

class AccountReport(models.Model):
    _inherit = 'account.report'

    filter_salesperson = fields.Boolean(
        string="Sales Persons",
        compute=lambda x: x._compute_report_option_filter('filter_salesperson'), readonly=False, store=True, depends=['root_report_id'],
    )

    filter_salesperson_hierarchy = fields.Selection(
        string="Group by Salesperson",
        selection=[('by_default', "Enabled by Default"), ('optional', "Optional"), ('never', "Never")],
        compute=lambda x: x._compute_report_option_filter('filter_salesperson_hierarchy', 'never'), readonly=False, store=True, depends=['root_report_id', 'section_main_report_ids'],
    )

    @api.model
    def _init_options_salesperson(self, options, previous_options=None):
        if not self.filter_salesperson:
            return
        options['salesperson'] = True
        options['salesperson_ids'] = previous_options and previous_options.get('salesperson_ids') or []
        selected_salesperson_ids = [int(partner) for partner in options['salesperson_ids']]
        selected_salespersons = selected_salesperson_ids and self.env['res.users'].browse(selected_salesperson_ids) or self.env['res.users']
        options['selected_salesperson_ids'] = selected_salespersons.mapped('name')

    @api.model
    def _get_options_salesperson_domain(self, options):
        domain = []
        if options.get('salesperson_ids'):
            salesperson_ids = [int(salesperson) for salesperson in options['salesperson_ids']]
            domain.append(('partner_id.user_id', 'in', salesperson_ids))
        return domain

    @api.model
    def _get_options_domain(self, options, date_scope):
        # OVERRIDE
        domain = super(AccountReport, self)._get_options_domain(options, date_scope)
        domain += self._get_options_salesperson_domain(options)
        return domain

    ####################################################
    # OPTIONS: hierarchy
    ####################################################

    def _init_options_salesperson_hierarchy(self, options, previous_options):
        company_ids = self.get_report_company_ids(options)
        if self.filter_salesperson_hierarchy != 'never':
            options['display_salesperson_hierarchy_filter'] = True
            if 'salesperson_hierarchy' in previous_options:
                options['salesperson_hierarchy'] = previous_options['salesperson_hierarchy']
            else:
                options['salesperson_hierarchy'] = self.filter_salesperson_hierarchy == 'by_default'
        else:
            options['salesperson_hierarchy'] = False
            options['display_salesperson_hierarchy_filter'] = False

    @api.model
    def _create_salesperson_hierarchy(self, lines, options):
        """Compute the hierarchy based on salesperson when the option is activated.

        It should be called when before returning the lines to the client/templater.
        The lines are the result of _get_lines(). If there is a hierarchy, it is left
        untouched, only the lines related to an res.partenr are put in a hierarchy
        according to the (salespersn)res.users's and their prefixes.
        """
        if not lines:
            return lines

        def get_salesperson_hierarchy(partner):
            # Create codes path in the hierarchy based on partner.
            salespersons = self.env['res.users']
            if partner.user_id:
                salesperson = partner.user_id
                salespersons += salesperson
            return list(salespersons.sorted(reverse=True))

        def create_hierarchy_line(salesperson, column_totals, level, parent_id):
            line_id = self._get_generic_line_id('res.users', salesperson.id if salesperson else None, parent_line_id=parent_id)
            unfolded = line_id in options.get('unfolded_lines') or options['unfold_all']
            name = salesperson.display_name if salesperson else _('(No Salesperson)')
            columns = []
            for column_total, column in zip(column_totals, options['columns']):
                columns.append(self._build_column_dict(column_total, column, options=options))
            return {
                'id': line_id,
                'name': name,
                'title_hover': name,
                'unfoldable': True,
                'unfolded': unfolded,
                'level': level,
                'parent_id': parent_id,
                'columns': columns,
            }

        def compute_salesperson_totals(line, salesperson=None):
            return [
                hierarchy_total + (column.get('no_format') or 0.0) if isinstance(hierarchy_total, float) else hierarchy_total
                for hierarchy_total, column
                in zip(hierarchy[salesperson]['totals'], line['columns'])
            ]

        def render_lines(salespersons, current_level, parent_line_id, skip_no_salesperson=True):
            to_treat = [(current_level, parent_line_id, salesperson) for salesperson in salespersons.sorted()]

            if None in hierarchy and not skip_no_salesperson:
                to_treat.append((current_level, parent_line_id, None))

            while to_treat:
                level_to_apply, parent_id, salesperson = to_treat.pop(0)
                salesperson_data = hierarchy[salesperson]
                hierarchy_line = create_hierarchy_line(salesperson, salesperson_data['totals'], level_to_apply, parent_id)
                new_lines.append(hierarchy_line)
                treated_child_salespersons = self.env['res.users']

                for salesperson_line in salesperson_data['lines']:
                    for child_salesperson in salesperson_data['child_salespersons']:
                        if child_salesperson not in treated_child_salespersons and child_salesperson['code_prefix_end'] < salesperson_line['name']:
                            render_lines(child_salesperson, hierarchy_line['level'] + 1, hierarchy_line['id'])
                            treated_child_salespersons += child_salesperson

                    markup, model, user_id = self._parse_line_id(salesperson_line['id'])[-1]
                    salesperson_line_id = self._get_generic_line_id(model, user_id, markup=markup, parent_line_id=hierarchy_line['id'])
                    salesperson_line.update({
                        'id': salesperson_line_id,
                        'parent_id': hierarchy_line['id'],
                        'level': hierarchy_line['level'] + 1,
                    })
                    new_lines.append(salesperson_line)

                    for child_line in salesperson_line_children_map[user_id]:
                        markup, model, res_id = self._parse_line_id(child_line['id'])[-1]
                        child_line.update({
                            'id': self._get_generic_line_id(model, res_id, markup=markup, parent_line_id=salesperson_line_id),
                            'parent_id': salesperson_line_id,
                            'level': salesperson_line['level'] + 1,
                        })
                        new_lines.append(child_line)

                to_treat = [
                    (level_to_apply + 1, hierarchy_line['id'], child_salesperson)
                    for child_salesperson
                    in salesperson_data['child_salespersons'].sorted()
                    if child_salesperson not in treated_child_salespersons
                ] + to_treat

        def create_hierarchy_dict():
            return defaultdict(lambda: {
                'lines': [],
                'totals': [('' if column.get('figure_type') == 'string' else 0.0) for column in options['columns']],
                'child_salespersons': self.env['res.users'],
            })

        # Precompute the salespersons of the partners in the report
        partner_ids = []
        for line in lines:
            markup, res_model, model_id = self._parse_line_id(line['id'])[-1]
            if res_model == 'res.partner':
                partner_ids.append(model_id)
        self.env['res.partner'].browse(partner_ids).user_id

        new_lines, total_lines = [], []

        # root_line_id is the id of the parent line of the lines we want to render
        root_line_id = self._build_parent_line_id(self._parse_line_id(lines[0]['id'])) or None
        last_salesperson_line_id = user_id = None
        current_level = 0
        salesperson_line_children_map = defaultdict(list)
        salespersons = self.env['res.users']
        root_salespersons = self.env['res.users']
        hierarchy = create_hierarchy_dict()

        for line in lines:
            markup, res_model, model_id = self._parse_line_id(line['id'])[-1]

            # Account lines are used as the basis for the computation of the hierarchy.
            if res_model == 'res.partner':
                last_salesperson_line_id = line['id']
                current_level = line['level']
                user_id = model_id
                user = self.env[res_model].browse(user_id)
                salespersons = get_salesperson_hierarchy(user)

                if not salespersons:
                    hierarchy[None]['lines'].append(line)
                    hierarchy[None]['totals'] = compute_salesperson_totals(line)
                else:
                    for i, salesperson in enumerate(salespersons):
                        if i == 0:
                            hierarchy[salesperson]['lines'].append(line)
                        if i == len(salespersons) - 1 and salesperson not in root_salespersons:
                            root_salespersons += salesperson
                        if salesperson.parent_id and salesperson not in hierarchy[salesperson.parent_id]['child_salespersons']:
                            hierarchy[salesperson.parent_id]['child_salespersons'] += salesperson

                        hierarchy[salesperson]['totals'] = compute_salesperson_totals(line, salesperson=salesperson)

            # This is not an account line, so we check to see if it is a descendant of the last account line.
            # If so, it is added to the mapping of the lines that are related to this salesperson.
            elif last_salesperson_line_id and line.get('parent_id', '').startswith(last_salesperson_line_id):
                salesperson_line_children_map[user_id].append(line)

            # This is a total line that is not linked to an salesperson. It is saved in order to be added at the end.
            elif markup == 'total':
                total_lines.append(line)

            # This line ends the scope of the current hierarchy and is (possibly) the root of a new hierarchy.
            # We render the current hierarchy and set up to build a new hierarchy
            else:
                render_lines(root_salespersons, current_level, root_line_id, skip_no_salesperson=False)

                new_lines.append(line)

                # Reset the hierarchy-related variables for a new hierarchy
                root_line_id = line['id']
                last_salesperson_line_id = user_id = None
                current_level = 0
                salesperson_line_children_map = defaultdict(list)
                root_salespersons = self.env['res.users']
                salespersons = self.env['res.users']
                hierarchy = create_hierarchy_dict()

        render_lines(root_salespersons, current_level, root_line_id, skip_no_salesperson=False)

        return new_lines + total_lines

    def _get_lines(self, options, all_column_groups_expression_totals=None, warnings=None):
        self.ensure_one()

        if options['report_id'] != self.id:
            # Should never happen; just there to prevent BIG issues and directly spot them
            raise UserError(_("Inconsistent report_id in options dictionary. Options says %(options_report)s; report is %(report)s.", options_report=options['report_id'], report=self.id))

        # Necessary to ensure consistency of the data if some of them haven't been written in database yet
        self.env.flush_all()

        if warnings is not None:
            self._generate_common_warnings(options, warnings)

        # Merge static and dynamic lines in a common list
        if all_column_groups_expression_totals is None:
            self._init_currency_table(options)
            all_column_groups_expression_totals = self._compute_expression_totals_for_each_column_group(
                self.line_ids.expression_ids,
                options,
                warnings=warnings,
            )

        dynamic_lines = self._get_dynamic_lines(options, all_column_groups_expression_totals, warnings=warnings)

        lines = []
        line_cache = {} # {report_line: report line dict}
        hide_if_zero_lines = self.env['account.report.line']

        # There are two types of lines:
        # - static lines: the ones generated from self.line_ids
        # - dynamic lines: the ones generated from a call to the functions referred to by self.dynamic_lines_generator
        # This loops combines both types of lines together within the lines list
        for line in self.line_ids: # _order ensures the sequence of the lines
            # Inject all the dynamic lines whose sequence is inferior to the next static line to add
            while dynamic_lines and line.sequence > dynamic_lines[0][0]:
                lines.append(dynamic_lines.pop(0)[1])

            parent_generic_id = None

            if line.parent_id:
                # Normally, the parent line has necessarily been treated in a previous iteration
                try:
                    parent_generic_id = line_cache[line.parent_id]['id']
                except KeyError as e:
                    raise UserError(_(
                        "Line '%(child)s' is configured to appear before its parent '%(parent)s'. This is not allowed.",
                        child=line.name, parent=e.args[0].name
                    ))

            line_dict = self._get_static_line_dict(options, line, all_column_groups_expression_totals, parent_id=parent_generic_id)
            line_cache[line] = line_dict

            if line.hide_if_zero:
                hide_if_zero_lines += line

            lines.append(line_dict)

        for dummy, left_dynamic_line in dynamic_lines:
            lines.append(left_dynamic_line)

        # Manage growth comparison
        if options.get('column_percent_comparison') == 'growth':
            for line in lines:
                first_value, second_value = line['columns'][0]['no_format'], line['columns'][1]['no_format']

                green_on_positive = True
                model, line_id = self._get_model_info_from_id(line['id'])

                if model == 'account.report.line' and line_id:
                    report_line = self.env['account.report.line'].browse(line_id)
                    compared_expression = report_line.expression_ids.filtered(
                        lambda expr: expr.label == line['columns'][0]['expression_label']
                    )
                    green_on_positive = compared_expression.green_on_positive

                line['column_percent_comparison_data'] = self._compute_column_percent_comparison_data(
                    options, first_value, second_value, green_on_positive=green_on_positive
                )
        # Manage budget comparison
        elif options.get('column_percent_comparison') == 'budget':
            for line in lines:
                self._set_budget_column_comparisons(options, line)

        # Manage hide_if_zero lines:
        # - If they have column values: hide them if all those values are 0 (or empty)
        # - If they don't: hide them if all their children's column values are 0 (or empty)
        # Also, hide all the children of a hidden line.
        hidden_lines_dict_ids = set()
        for line in hide_if_zero_lines:
            children_to_check = line
            current = line
            while current:
                children_to_check |= current
                current = current.children_ids

            all_children_zero = True
            hide_candidates = set()
            for child in children_to_check:
                child_line_dict_id = line_cache[child]['id']

                if child_line_dict_id in hidden_lines_dict_ids:
                    continue
                elif all(col.get('is_zero', True) for col in line_cache[child]['columns']):
                    hide_candidates.add(child_line_dict_id)
                else:
                    all_children_zero = False
                    break

            if all_children_zero:
                hidden_lines_dict_ids |= hide_candidates

        lines[:] = filter(lambda x: x['id'] not in hidden_lines_dict_ids and x.get('parent_id') not in hidden_lines_dict_ids, lines)

        # Create the hierarchy of lines if necessary
        if options.get('hierarchy'):
            lines = self._create_hierarchy(lines, options)

        # Customization added by this app
        # Create the salesperson hierarchy of lines if necessary
        if options.get('salesperson_hierarchy'):
            lines = self._create_salesperson_hierarchy(lines, options)

        # Handle totals below sections for static lines
        lines = self._add_totals_below_sections(lines, options)

        # Unfold lines (static or dynamic) if necessary and add totals below section to dynamic lines
        lines = self._fully_unfold_lines_if_needed(lines, options)

        if self.custom_handler_model_id:
            lines = self.env[self.custom_handler_model_name]._custom_line_postprocessor(self, options, lines)

        if warnings is not None:
            custom_handler_name = self.custom_handler_model_name or self.root_report_id.custom_handler_model_name
            if custom_handler_name:
                self.env[custom_handler_name]._customize_warnings(self, options, all_column_groups_expression_totals, warnings)

        # Format values in columns of lines that will be displayed
        self._format_column_values(options, lines)

        if options.get('export_mode') == 'print' and options.get('hide_0_lines'):
            lines = self._filter_out_0_lines(lines)

        return lines

    def get_report_information(self, options):
        result = super().get_report_information(options)
        result['filters']['show_salesperson_hierarchy'] = options.get('display_salesperson_hierarchy_filter', False)
        return result

class AccountReportLine(models.Model):
    _inherit = 'account.report.line'

    def _expand_groupby(self, line_dict_id, groupby, options, offset=0, limit=None, load_one_more=False, unfold_all_batch_data=None):
        """ Expand function used to get the sublines of a groupby.
        groupby param is a string consisting of one or more coma-separated field names. Only the first one
        will be used for the expansion; if there are subsequent ones, the generated lines will themselves used them as
        their groupby value, and point to this expand_function, hence generating a hierarchy of groupby).
        """
        self.ensure_one()
        salesperson_lines = super()._expand_groupby(line_dict_id, groupby, options, offset=offset, limit=limit, load_one_more=load_one_more, unfold_all_batch_data=unfold_all_batch_data)
        
        # Customization added by this app
        if options.get('salesperson_hierarchy'):
            salesperson_lines = self.report_id._create_salesperson_hierarchy(salesperson_lines, options)

        return salesperson_lines
