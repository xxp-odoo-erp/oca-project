# Copyright 2024 Odoo Community Association (OCA)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from odoo.addons.base.tests.common import HttpCaseWithUserPortal
from odoo.addons.project.tests.test_access_rights import TestProjectPortalCommon


@tagged("post_install", "-at_install")
class TestProjectPortalTaskCreation(TestProjectPortalCommon, HttpCaseWithUserPortal):
    @classmethod
    def setUpClass(cls):
        super(TestProjectPortalTaskCreation, cls).setUpClass()

        # Create test project
        cls.project = cls.env["project.project"].create(
            {
                "name": "Test Project",
                "description": "Test project for portal task creation",
            }
        )

        # Create test stages
        cls.stage_backlog = cls.env["project.task.type"].create(
            {
                "name": "Backlog",
                "project_ids": [(6, 0, [cls.project.id])],
            }
        )

        cls.stage_in_progress = cls.env["project.task.type"].create(
            {
                "name": "In Progress",
                "project_ids": [(6, 0, [cls.project.id])],
            }
        )

        # Set portal task creation stage
        cls.project.portal_stage_id = cls.stage_backlog

        # Set portal allowed users
        cls.project.portal_user_ids = cls.user_portal

    def test_project_portal_task_creation_allowed(self):
        # Project with portal stage should allow creation
        user_project = self.project.with_user(self.user_portal).sudo()
        self.assertTrue(user_project.is_portal_task_creation_allowed())
        # we set no followers option, only project.portal_user_ids can create
        user_project.portal_user_ids = False
        user_project.all_project_followers_can_create = False
        self.assertFalse(user_project.is_portal_task_creation_allowed())
        user_project.portal_stage_id = self.stage_backlog
        user_project.portal_user_ids = False
        self.assertFalse(user_project.is_portal_task_creation_allowed())
        # now we set followers to be allowed to create
        user_project.all_project_followers_can_create = True
        user_project.message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        self.assertTrue(user_project.is_portal_task_creation_allowed())

    def test_project_portal_task_editing_allowed(self):
        # Project with portal stage should allow editing
        user_project = self.project.with_user(self.user_portal).sudo()
        # we set no followers option, only project.portal_user_ids can edit
        user_project.all_project_followers_can_edit = False
        self.assertTrue(user_project.is_portal_task_editing_allowed())
        # Project without portal stage should allow editing
        user_project.portal_stage_id = False
        self.assertTrue(user_project.is_portal_task_editing_allowed())
        # No portal user id, and no followers editing
        user_project.portal_user_ids = False
        self.assertFalse(user_project.is_portal_task_editing_allowed())
        # now we set followers to be allowed to create
        user_project.all_project_followers_can_edit = True
        user_project.message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        self.assertTrue(user_project.is_portal_task_editing_allowed())

    def test_task_portal_creation(self):
        """Test task creation by portal user."""
        # Create task as portal user
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Portal Task",
                    "description": "Task created by portal user",
                    "project_id": self.project.id,
                }
            )
        )
        # Check that task was created with correct settings
        self.assertEqual(task.name, "Portal Task")
        self.assertEqual(task.project_id, self.project)
        # default stage set.
        self.assertEqual(task.stage_id, self.stage_backlog)
        self.assertEqual(task.create_uid, self.user_portal)

    def test_task_portal_edit_own_task(self):
        """Test portal user editing their own task."""
        # Create task as portal user
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Portal Task",
                    "description": "Task created by portal user",
                    "project_id": self.project.id,
                }
            )
        )

        # Edit task as portal user
        task.with_user(self.user_portal).sudo().write(
            {
                "name": "Updated Portal Task",
                "description": "Updated description",
            }
        )

        # Check that task was updated
        self.assertEqual(task.name, "Updated Portal Task")
        self.assertIn("Updated description", task.description)

    def test_task_portal_edit_other_user_task(self):
        """Test portal user trying to edit another user's task."""
        # Create task as internal user
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Internal Task",
                    "description": "Task created by internal user",
                    "project_id": self.project.id,
                }
            )
        )

        self.project.portal_user_ids = False

        # Try to edit task as portal user
        self.project.all_project_followers_can_edit = False
        with self.assertRaises(AccessError):
            task.with_user(self.user_portal).sudo().write(
                {
                    "name": "Hacked Task",
                }
            )

    def test_task_portal_edit_wrong_stage(self):
        """Test portal user trying to edit task in wrong stage."""
        # Create task as portal user
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Portal Task",
                    "description": "Task created by portal user",
                    "project_id": self.project.id,
                }
            )
        )

        # Move task to different stage
        task.stage_id = self.stage_in_progress

        # Try to edit task as portal user
        with self.assertRaises(AccessError):
            task.with_user(self.user_portal).write(
                {
                    "name": "Updated Task",
                }
            )

    def test_check_portal_fields_access(self):
        """Test _check_portal_fields_access method returns correct fields."""
        Project = self.env["project.project"]
        allowed_fields = Project.all_portal_task_fields()
        # Check that the method returns expected fields
        self.assertIsInstance(allowed_fields, list)
        self.assertIn("name", allowed_fields)
        self.assertIn("description", allowed_fields)
        self.assertIn("date_deadline", allowed_fields)
        self.assertIn("priority", allowed_fields)
        self.assertIn("stage_id", allowed_fields)
        self.assertEqual(len(allowed_fields), 5)

    def test_check_portal_edit_access_allowed(self):
        """Test check_portal_edit_access when access is allowed."""
        # Create task as portal user
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Portal Task",
                    "description": "Task created by portal user",
                    "project_id": self.project.id,
                }
            )
        )

        # Check that portal user has edit access to their own task
        self.assertTrue(task.with_user(self.user_portal).check_portal_edit_access())

    def test_check_portal_edit_access_denied_not_creator(self):
        """Test check_portal_edit_access denied when user is not the creator."""
        # Create task as admin
        task = self.env["project.task"].create(
            {
                "name": "Admin Task",
                "description": "Task created by admin",
                "project_id": self.project.id,
                "stage_id": self.stage_backlog.id,
            }
        )
        self.project.edit_only_creator = True
        # Check that portal user has no edit access to admin's task
        self.assertFalse(
            task.with_user(self.user_portal).sudo().check_portal_edit_access()
        )

    def test_create_task_as_portal_clears_assignees(self):
        """Test that creating a task as portal user clears user_ids."""
        admin_user = self.env.ref("base.user_admin")
        # Create task as portal user with user_ids
        task = (
            self.env["project.task"]
            .with_user(self.user_portal)
            .sudo()
            .create(
                {
                    "name": "Portal Task",
                    "description": "Task created by portal user",
                    "project_id": self.project.id,
                    "user_ids": [(6, 0, [admin_user.id])],
                }
            )
        )

        # Check that user_ids is empty
        self.assertFalse(task.user_ids)

    def test_create_task_as_internal_user_keeps_assignees(self):
        """Test that creating a task as internal user keeps user_ids."""
        admin_user = self.env.ref("base.user_admin")
        # Create task as internal user with user_ids
        task = self.env["project.task"].create(
            {
                "name": "Admin Task",
                "description": "Task created by admin",
                "project_id": self.project.id,
                "user_ids": [(6, 0, [admin_user.id])],
            }
        )

        # Check that user_ids is preserved
        self.assertTrue(task.user_ids)
        self.assertIn(admin_user, task.user_ids)

    def test_creation_and_edit_rights(self):
        # By default, portal user is not allowed (no portal_user_ids or stage set)
        self.project.all_project_followers_can_create = False
        self.project.portal_user_ids = [(6, 0, [])]
        self.assertFalse(
            self.project.with_user(
                self.user_portal.id
            ).is_portal_task_creation_allowed()
        )
        self.assertFalse(
            self.project.with_user(self.user_portal.id).is_portal_task_editing_allowed()
        )

        # Add portal user to allowed users
        self.project.sudo().write({"portal_user_ids": [(4, self.user_portal.id)]})
        # Now portal user can create/edit (portal_stage_id must be set)
        self.assertTrue(
            self.project.with_user(
                self.user_portal.id
            ).is_portal_task_creation_allowed()
        )
        self.assertTrue(
            self.project.with_user(self.user_portal.id).is_portal_task_editing_allowed()
        )

    def test_followers_creation_with_flag(self):
        # Enable creation for all followers only
        self.project.sudo().write(
            {"portal_user_ids": [(5,)], "all_project_followers_can_create": True}
        )
        # Subscribe portal user's partner as follower
        self.project.message_subscribe(partner_ids=[self.user_portal.partner_id.id])
        # Now portal user (as follower) is allowed to create
        self.assertTrue(
            self.project.with_user(
                self.user_portal.id
            ).is_portal_task_creation_allowed()
        )

    def test_portal_fields_constraints(self):
        # By default, 'description' must be in portal_create_task_fields
        field_names = self.project.portal_create_task_fields.mapped("name")
        self.assertIn("description", field_names)
        # Removing 'description' should raise ValidationError
        desc_field = self.env["ir.model.fields"].search(
            [("model", "=", "project.task"), ("name", "=", "description")], limit=1
        )
        # Remove all fields except description (forcing violation)
        other_fields = [
            f.id for f in self.project.portal_create_task_fields if f != desc_field
        ]
        with self.assertRaises(ValidationError):
            self.project.portal_create_task_fields = [(6, 0, other_fields)]
