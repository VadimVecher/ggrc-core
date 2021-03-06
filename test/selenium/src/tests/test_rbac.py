# Copyright (C) 2018 Google Inc.
# Licensed under http://www.apache.org/licenses/LICENSE-2.0 <see LICENSE file>
"""Tests for RBAC"""
# pylint: disable=no-self-use

import pytest

from lib import base, users
from lib.constants import roles, object_states
from lib.entities import entities_factory
from lib.service import rest_facade, webui_facade, webui_service
from lib.utils import string_utils


class TestRBAC(base.Test):
  """Tests for RBAC"""

  ALL_ROLES = [roles.CREATOR, roles.READER, roles.EDITOR, roles.ADMINISTRATOR]

  @pytest.fixture()
  def users_with_all_roles(self):
    return {role: rest_facade.create_user_with_role(role_name=role)
            for role in self.ALL_ROLES}

  @pytest.mark.smoke_tests
  @pytest.mark.parametrize(
      "role",
      [roles.CREATOR, roles.READER, roles.EDITOR]
  )
  def test_object_creation(self, role, selenium):
    """Test that users with all global roles can create, then edit and delete
    objects.
    """
    user = rest_facade.create_user_with_role(role_name=role)
    users.set_current_user(user)
    objs = [rest_facade.create_program(), rest_facade.create_control()]
    for obj in objs:
      webui_facade.assert_can_edit(selenium, obj, can_edit=True)
      webui_facade.assert_can_delete(selenium, obj, can_delete=True)

  @pytest.mark.smoke_tests
  @pytest.mark.parametrize(
      "login_role, can_view, can_edit",
      [
          (roles.CREATOR, False, False),
          (roles.READER, True, False),
          (roles.EDITOR, True, True)
      ]
  )
  def test_permissions(
      self, users_with_all_roles, login_role, can_view, can_edit, selenium
  ):  # pylint: disable=too-many-arguments
    """Test that users have permissions to objects created by other users
    according to their global role.
    """
    objs = []
    other_roles = [role for role in self.ALL_ROLES if role != login_role]
    for role in other_roles:
      users.set_current_user(users_with_all_roles[role])
      program = rest_facade.create_program()
      control = rest_facade.create_control(program)
      objs.extend([program, control])
    users.set_current_user(users_with_all_roles[login_role])
    for obj in objs:
      if can_view:
        webui_facade.assert_can_view(selenium, obj)
        webui_facade.assert_can_edit(selenium, obj, can_edit=can_edit)
        webui_facade.assert_can_delete(selenium, obj, can_delete=can_edit)
      else:
        webui_facade.assert_cannot_view(selenium, obj)

  @pytest.mark.smoke_tests
  @pytest.mark.parametrize(
      "login_role",
      [roles.CREATOR, roles.READER]
  )
  @pytest.mark.parametrize(
      "obj, obj_role",
      [
          ("audit", "auditors"),
          ("assessment", "assignees"),
          ("assessment", "verifiers")
      ]
  )
  def test_add_evidence_url(
      self, program, login_role, obj, obj_role, selenium
  ):
    """Test that various users have possibility to add an evidence url into
    assessment.
    """
    login_user = rest_facade.create_user_with_role(login_role)
    obj_args = {obj_role: [login_user]}
    audit = rest_facade.create_audit(
        program, **obj_args if obj == "audit" else {})
    asmt = rest_facade.create_assessment(
        audit, **obj_args if obj == "assessment" else {})
    users.set_current_user(login_user)
    url = string_utils.StringMethods.random_string()
    asmt_service = webui_service.AssessmentsService(selenium)
    asmt_service.add_evidence_url(asmt, [url])
    actual_asmt = asmt_service.get_obj_from_info_page(obj=asmt)
    asmt.update_attrs(
        updated_at=rest_facade.get_obj(asmt).updated_at,
        status=object_states.IN_PROGRESS,
        evidence_urls=[url]).repr_ui()
    self.general_equal_assert(asmt, actual_asmt, "audit")


class TestAuditorRole(base.Test):
  """Tests for auditor role."""

  @pytest.fixture(autouse=True, scope="class")
  def set_superuser_as_current_user(self):
    """Class fixtures are evaluated before function fixtures.
    This fixture is used by class `test_data` fixture so this one should be
    class as well.
    Code is copied from conftest.py.
    """
    # pylint: disable=protected-access
    users._current_user = users.FakeSuperUser()
    users.set_current_user(entities_factory.PeopleFactory.superuser)

  @pytest.fixture(scope="class")
  def test_data(self):
    """Objects structure:
    Program
    -> Control
    -> Audit (Auditor is a user with global creator role)
    """
    editor = rest_facade.create_user_with_role(roles.EDITOR)
    creator = rest_facade.create_user_with_role(roles.CREATOR)
    users.set_current_user(editor)
    program = rest_facade.create_program()
    control = rest_facade.create_control(program=program)
    audit = rest_facade.create_audit(program, auditors=[creator])
    return {
        "editor": editor,
        "creator": creator,
        "program": program,
        "audit": audit,
        "control": control
    }

  @pytest.mark.smoke_tests
  def test_auditor_cannot_edit_audit(
      self, selenium, test_data
  ):
    """Test that Auditor cannot edit audit"""
    creator = test_data["creator"]
    users.set_current_user(creator)
    audit = test_data["audit"]
    webui_facade.assert_can_view(selenium, audit)
    webui_facade.assert_can_edit(selenium, audit, can_edit=False)

  @pytest.mark.smoke_tests
  def test_auditor_cannot_view_control(
      self, selenium, test_data
  ):
    """Test that Auditor cannot view control"""
    creator = test_data["creator"]
    users.set_current_user(creator)
    control = test_data["control"]
    webui_facade.assert_cannot_view(selenium, control)
