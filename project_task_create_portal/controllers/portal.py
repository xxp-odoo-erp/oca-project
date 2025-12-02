from datetime import timedelta

from odoo import _, http
from odoo.exceptions import AccessError, MissingError
from odoo.fields import Date, Datetime
from odoo.http import request

from odoo.addons.project.controllers.portal import ProjectCustomerPortal


class ProjectCustomerNewPortal(ProjectCustomerPortal):
    @property
    def mandatory_task_fields(self) -> list:
        # mandatory fields on create is description
        # if name, prio, stage or deadline are missing , defaults will be given
        return ["description"]

    def get_default_values(self, fieldname, project):
        default = False
        # this modules specifies a specific per-project default stage, if none is
        # specified
        if fieldname == "stage_id":
            # editing and creation would not be allowed if default stage not set.
            default = project.portal_stage_id
        # priority and stage have defaults
        if fieldname == "priority":
            request.env["project.task"].default_get(["priority"])["priority"]
        if not default:
            if fieldname == "name":
                user_name = (
                    request.env["res.users"]
                    .sudo()
                    .browse(int(request.env.context.get("uid", request.env.user.id))
                    .name
                )
                default = f"Portal task from {user_name} generated on {Datetime.now()}"
                )
            if fieldname == "date_deadline":
                default = str(
                    Datetime.now() + timedelta(days=project.auto_portal_deadline)
                )
        return default

    def _validate_task_fields(self, data, task_creation=False) -> tuple:
        error, error_message = dict(), []
        # Validation
        for field_name in self.mandatory_task_fields:
            if not data.get(field_name) and task_creation:
                error[field_name] = "missing"
                error_message.append("Missing value for %s" % field_name)
        # Deadline validation
        date_deadline = data.get("date_deadline")
        if date_deadline:
            date = Date.to_date(data.get("date_deadline"))
            if date and date < Date.today():
                error["date_deadline"] = "invalid"
                error_message.append("Deadline is in the past")
        description = data.get("description")
        if description:
            if description.strip() == "":
                error["description"] = "invalid"
                error_message.append("Description Cannot be empty")
        return error, error_message

    def _prepare_task_values(self, data, mode="create") -> dict:
        """
        Prepare task values
        :param dict data: post values
        :return: prepared task values
        """
        values = {
            key: data[key]
            for key in request.env["project.project"].all_portal_task_fields()
            if key in data and data.get(key)
        }
        # note if other M2M/M2O fields were added we should generalize
        if "stage_id" in values:
            values["stage_id"] = int(values["stage_id"])
        return values

    def _task_action_page_view_values(self, project, mode="create") -> dict:
        """
        Prepare values for task action page view
        :param project: project.project
        :return: dict
        """
        values = self._prepare_portal_layout_values()
        stage_options = []
        stages = (
            request.env["project.task.type"]
            .sudo()
            .search([("id", "in", project.type_ids.ids)])
        )
        for stage in stages:
            stage_options.append({"id": stage.id, "name": stage.name})

        priority_selection = request.env["project.task"]._fields["priority"].selection
        values.update(
            {
                "project": project,
                # editable configuration per-project
                "priority_selection": priority_selection,
                "stage_options": stage_options,
                "mode": mode,
                "error": {},
                "error_message": [],
            }
        )
        if mode == "create":
            for field in project.all_portal_task_fields():
                values[
                    "editable_portal_" + field
                ] = field in project.portal_create_task_fields.mapped("name")
        if mode == "edit":
            for field in project.all_portal_task_fields():
                values[
                    "editable_portal_" + field
                ] = field in project.portal_edit_task_fields.mapped("name")
        for field in project.all_portal_task_fields():
            values["default_portal_" + field] = self.get_default_values(field, project)
        return values

    @http.route(
        ["/my/projects/<int:project_id>/task/new"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_project_create_task(self, project_id=None, **post) -> http.Response:
        """
        Create a task in a project
        :param int project_id: project
        :param dict post: post values
        """
        project = request.env["project.project"].sudo().browse(project_id).exists()
        if not project:
            raise MissingError(_("Project not found!"))
        if not project.is_portal_task_creation_allowed():
            raise AccessError(_("You are not allowed to create tasks in this project."))
        values = self._task_action_page_view_values(project, mode="create")
        if post and request.httprequest.method == "POST":
            error, error_message = self._validate_task_fields(post)
            if not error:
                values = self._prepare_task_values(post, mode="create")
                values.update(
                    stage_id=project.portal_stage_id.id,
                    partner_id=request.env.user.partner_id.id,
                    project_id=project.id,
                )
                task = request.env["project.task"].sudo().create(values)
                return request.redirect(f"/my/projects/{project_id}/task/{task.id}")
            values.update({"error": error, "error_message": error_message, **post})
        values.update({"page_name": "task_creation", "button": _("Create")})
        return request.render(
            "project_task_create_portal.portal_project_task_new", values
        )

    @http.route(
        ["/my/projects/<int:project_id>/task/<int:task_id>/edit"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_project_edit_task(self, project_id=None, task_id=None, **post):
        """
        Edit a task in a project
        :param int project_id: project.project record id
        :param int task_id: project.task record id
        :param dict post: post values
        """
        task = (
            request.env["project.task"]
            .sudo()
            .search([("id", "=", task_id), ("project_id", "=", project_id)])
        )
        if not task:
            raise MissingError(_("Task not found!"))
        if not task.project_id.is_portal_task_editing_allowed():
            raise AccessError(_("You are not allowed to edit this task."))
        values = self._task_action_page_view_values(task.project_id, mode="edit")
        values.update(
            {
                "task": task,
                "name": task.name,
                "description": task.description,
                "date_deadline": task.date_deadline,
                "priority": task.priority,
                "stage_id": task.stage_id.id,
                "button": _("Save"),
            }
        )
        if post and request.httprequest.method == "POST":
            error, error_message = self._validate_task_fields(post)
            if not error:
                task.sudo().write(self._prepare_task_values(post, mode="edit"))
                return request.redirect(f"/my/projects/{project_id}/task/{task_id}")
            values.update({"error": error, "error_message": error_message, **post})
        values.update({"page_name": "task_edit"})
        return request.render(
            "project_task_create_portal.portal_project_task_new", values
        )

    def _project_get_page_view_values(
        self,
        project,
        access_token,
        page=1,
        date_begin=None,
        date_end=None,
        sortby=None,
        search=None,
        search_in="content",
        groupby=None,
        **kwargs,
    ):
        values = super()._project_get_page_view_values(
            project,
            access_token,
            page,
            date_begin,
            date_end,
            sortby,
            search,
            search_in,
            groupby,
            **kwargs,
        )
        # Access to visible create task button in searchbar and project grouping header
        values[
            "searchbar_create_task"
        ] = project.sudo().is_portal_task_creation_allowed()
        return values

    def _task_get_searchbar_groupby(self, milestones_allowed):
        values = super()._task_get_searchbar_groupby(milestones_allowed)
        values.update(
            create_uid={"input": "create_uid", "label": _("Created by"), "order": 12}
        )
        return dict(sorted(values.items(), key=lambda item: item[1]["order"]))

    def _task_get_searchbar_sortings(self, milestones_allowed):
        values = super()._task_get_searchbar_sortings(milestones_allowed)
        values.update(
            create_date={
                "label": _("Created by"),
                "order": "create_uid desc",
                "sequence": 12,
            }
        )
        return values

    def _task_get_groupby_mapping(self):
        result = super()._task_get_groupby_mapping()
        result.update(create_uid="create_uid")
        return result
