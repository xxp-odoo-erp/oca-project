from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectProject(models.Model):
    _inherit = "project.project"

    @api.model
    def all_portal_task_fields(self) -> list:
        return [
            "name",
            "description",
            "date_deadline",
            "stage_id",
            "priority",
        ]

    portal_stage_id = fields.Many2one(
        "project.task.type",
        help="Stage from which portal users will be allowed to create and edit tasks.",
        domain="[('project_ids', 'in', [id])]",
    )
    portal_user_ids = fields.Many2many(
        "res.users",
        relation="portal_project_allowed_user_rel",
        column1="project_id",
        column2="user_id",
        domain=lambda self: [
            ("groups_id", "in", self.env.ref("base.group_portal").ids)
        ],
    )
    portal_hide_assigned_users = fields.Boolean(
        string="Hide Assigned User",
        help="If enabled, the portal assigned users will not be displayed in the project.",
    )
    all_project_followers_can_create = fields.Boolean()
    all_project_followers_can_edit = fields.Boolean()
    edit_only_creator = fields.Boolean(
        string="Edit only own Tasks",
        help="""if selected, all users with edit permissions will edit
                only the tasks they have created""",
    )

    portal_edit_task_fields = fields.Many2many(
        comodel_name="ir.model.fields",
        relation="project_optional_edit_task_fields_rel",
        column1="project_id",
        column2="field_id",
        string="Portal modifiable fields on task edit",
        domain=lambda self: self._get_task_field_domain(),
    )

    portal_create_task_fields = fields.Many2many(
        comodel_name="ir.model.fields",
        relation="project_optional_create_task_fields_rel",
        column1="project_id",
        column2="field_id",
        string="Portal modifiable fields on task create",
        default=lambda self: self._get_description_field(),
        domain=lambda self: self._get_task_field_domain(),
        help="""The selected fields will be editsable on create""",
    )
    auto_portal_deadline = fields.Integer(
        string="Days to automatic deadline",
        default=3,
        help="""When deadline is disabled on creation, insert here the amount
                of days from task creation to set the deadline""",
    )

    @api.model
    def _get_description_field(self):
        return self.env["ir.model.fields"].search(
            [
                ("model", "=", "project.task"),
                ("name", "=", "description"),
            ],
            limit=1,
        )

    @api.constrains("portal_create_task_fields")
    def _check_description_field_present(self):
        description_field = self._get_description_field()
        for project in self:
            if description_field not in project.portal_create_task_fields:
                raise ValidationError(
                    _(
                        "The 'description' field must always be enabled "
                        "in Portal Task Creation fields."
                    )
                )

    @api.model
    def _get_task_field_domain(self):
        allowed_fields = self.all_portal_task_fields()
        return [("model", "=", "project.task"), ("name", "in", allowed_fields)]

    def _check_portal_stage_id(self):
        """Ensure the portal task creation stage belongs to this project."""
        for project in self:
            stage = project.portal_stage_id
            if stage and stage not in project.type_ids:
                raise ValidationError(
                    _("The Portal Task Creation Stage must belong to this project.")
                )

    def is_portal_task_creation_allowed(self):
        self.ensure_one()
        self = self.sudo()
        valid_users = self.portal_user_ids.ids
        if self.all_project_followers_can_create:
            valid_users.extend(
                self.message_follower_ids.mapped("partner_id.user_ids").ids
            )
        # If context.uid is present,use it, this is protective against page value
        # sudoing from other modules.
        active_user = self.env.context.get("uid", self.env.user.id)
        return active_user in valid_users

    def is_portal_task_editing_allowed(self):
        self.ensure_one()
        self = self.sudo()
        valid_users = self.portal_user_ids.ids
        if self.all_project_followers_can_edit:
            valid_users.extend(
                self.message_follower_ids.mapped("partner_id.user_ids").ids
            )
        active_user = self.env.context.get("uid", self.env.user.id)
        return active_user in valid_users
