from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Project, Floor, Room, MilestoneDefinition, RoomMilestoneStatus, DefectInspection
from .floor_generator import (
    compute_floor_prefix,
    generate_apartment_numbers_list,
    preview_floor_plan,
    create_floor_with_apartments,
    update_floor_with_apartments,
    add_common_areas_to_floor,
    safe_delete_room,
)


class FloorApartmentGenerationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='test_engineer', password='password123')
        self.client = Client()
        self.client.login(username='test_engineer', password='password123')

        self.project = Project.objects.create(
            name="Test Burj Tower",
            pm_name="Eng. Test PM",
            mechanical_lead="Eng. Mech Lead",
            electrical_lead="Eng. Elec Lead",
            hvac_lead="Eng. HVAC Lead",
            total_floors=20
        )

        # Create milestone definitions
        self.m1 = MilestoneDefinition.objects.create(name="Suspension", category=MilestoneDefinition.CATEGORY_GENERAL, display_order=1)
        self.m2 = MilestoneDefinition.objects.create(name="First Fix", category=MilestoneDefinition.CATEGORY_GENERAL, display_order=2)
        self.m3 = MilestoneDefinition.objects.create(name="Civil High Wall Closing", category=MilestoneDefinition.CATEGORY_CIVIL, display_order=3)
        self.m4 = MilestoneDefinition.objects.create(name="False Ceiling Closure", category=MilestoneDefinition.CATEGORY_FITOUT, display_order=4)

    def test_prefix_computation(self):
        """Tests standard and custom prefix detection rules."""
        self.assertEqual(compute_floor_prefix('Floor 01', 'Typical Floor'), '01')
        self.assertEqual(compute_floor_prefix('Floor 05', 'Typical Floor'), '05')
        self.assertEqual(compute_floor_prefix('Floor 12', 'Typical Floor'), '12')
        self.assertEqual(compute_floor_prefix('Basement 1', 'Basement'), 'B1-')
        self.assertEqual(compute_floor_prefix('Podium 2', 'Podium'), 'P2-')
        self.assertEqual(compute_floor_prefix('Ground Floor', 'Ground Floor'), 'G')
        # Custom override
        self.assertEqual(compute_floor_prefix('Floor 05', 'Typical Floor', custom_prefix='T5-'), 'T5-')

    def test_apartment_number_generation(self):
        """Tests exact apartment list sequences required by specifications."""
        # Floor 01 + 12 apartments -> 0101 to 0112
        apts_01 = generate_apartment_numbers_list('01', 12, starting_number=1)
        self.assertEqual(len(apts_01), 12)
        self.assertEqual(apts_01[0], '0101')
        self.assertEqual(apts_01[-1], '0112')

        # Floor 05 + 16 apartments -> 0501 to 0516
        apts_05 = generate_apartment_numbers_list('05', 16, starting_number=1)
        self.assertEqual(len(apts_05), 16)
        expected_05 = [
            '0501', '0502', '0503', '0504', '0505', '0506', '0507', '0508',
            '0509', '0510', '0511', '0512', '0513', '0514', '0515', '0516'
        ]
        self.assertEqual(apts_05, expected_05)

        # Floor 12 + 20 apartments -> 1201 to 1220
        apts_12 = generate_apartment_numbers_list('12', 20, starting_number=1)
        self.assertEqual(len(apts_12), 20)
        self.assertEqual(apts_12[0], '1201')
        self.assertEqual(apts_12[-1], '1220')

        # Basement 1 + 6 apartments -> B1-01 to B1-06
        apts_b1 = generate_apartment_numbers_list('B1-', 6, starting_number=1)
        self.assertEqual(apts_b1, ['B1-01', 'B1-02', 'B1-03', 'B1-04', 'B1-05', 'B1-06'])

    def test_create_floor_with_apartments_and_milestones(self):
        """Verifies creating Floor 05 with 16 apartments and common areas in a transaction."""
        common_areas = ['Lift Lobby', 'Corridor', 'Garbage Room', 'HVAC Room']
        res = create_floor_with_apartments(
            project=self.project,
            floor_number="Floor 05",
            floor_type=Floor.FLOOR_TYPE_TYPICAL,
            apartment_count=16,
            starting_number=1,
            common_areas=common_areas,
        )
        floor = res['floor']
        self.assertEqual(floor.total_apartments, 16)
        self.assertEqual(floor.total_common_areas, 4)
        self.assertEqual(floor.total_rooms, 20)

        # Verify common areas are not counted as apartments
        apts = floor.apartments.values_list('room_number', flat=True)
        self.assertIn('0501', apts)
        self.assertIn('0516', apts)
        self.assertNotIn('Lift Lobby', apts)

        # Verify milestones initialized to Pending for all rooms
        for r in floor.rooms.all():
            statuses = list(r.milestones.values_list('status', flat=True))
            self.assertEqual(len(statuses), 4)  # 4 definitions
            self.assertTrue(all(s == RoomMilestoneStatus.STATUS_PENDING for s in statuses))

    def test_duplicate_safe_idempotency(self):
        """Calling floor creation multiple times does not produce duplicate rooms or statuses."""
        create_floor_with_apartments(self.project, "Floor 05", Floor.FLOOR_TYPE_TYPICAL, 16)
        # Call again with identical data
        create_floor_with_apartments(self.project, "Floor 05", Floor.FLOOR_TYPE_TYPICAL, 16)

        floor = Floor.objects.get(project=self.project, floor_number="Floor 05")
        self.assertEqual(floor.total_apartments, 16)
        self.assertEqual(RoomMilestoneStatus.objects.filter(room__floor=floor).count(), 16 * 4)

    def test_zero_apartment_count_allowed(self):
        """Zero apartments creates the floor with common areas only."""
        res = create_floor_with_apartments(
            project=self.project,
            floor_number="Mechanical Level 1",
            floor_type=Floor.FLOOR_TYPE_MECHANICAL,
            apartment_count=0,
            common_areas=['HVAC Room', 'Electrical Room']
        )
        floor = res['floor']
        self.assertEqual(floor.total_apartments, 0)
        self.assertEqual(floor.total_common_areas, 2)
        self.assertEqual(floor.total_rooms, 2)

    def test_edit_floor_increase_count(self):
        """Increasing count generates only missing units, preserving existing units and defects."""
        res1 = create_floor_with_apartments(self.project, "Floor 08", Floor.FLOOR_TYPE_TYPICAL, 10)
        floor = res1['floor']
        self.assertEqual(floor.total_apartments, 10)

        # Increase count to 14
        res2 = update_floor_with_apartments(floor, "Floor 08", Floor.FLOOR_TYPE_TYPICAL, 14)
        self.assertEqual(floor.total_apartments, 14)
        self.assertEqual(len(res2['newly_created']), 4)
        new_names = [r.room_number for r in res2['newly_created']]
        self.assertEqual(new_names, ['0811', '0812', '0813', '0814'])

    def test_edit_floor_decrease_with_defect_protection(self):
        """Rooms with defect inspections are NEVER deleted when count decreases."""
        res = create_floor_with_apartments(self.project, "Floor 09", Floor.FLOOR_TYPE_TYPICAL, 10)
        floor = res['floor']

        # Add a defect inspection to room 0910
        room_0910 = Room.objects.get(floor=floor, room_number='0910')
        DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            room=room_0910,
            department=DefectInspection.DEPARTMENT_HVAC,
            faults_description="Duct leakage near collar",
            status=DefectInspection.STATUS_NCR
        )

        # Attempt to decrease count to 8 with confirmation
        update_res = update_floor_with_apartments(
            floor=floor,
            floor_number="Floor 09",
            floor_type=Floor.FLOOR_TYPE_TYPICAL,
            apartment_count=8,
            confirm_removal=True
        )

        # Room 0909 has 0 defects and should be deleted
        self.assertIn('0909', update_res['deleted_rooms'])
        # Room 0910 has defect and MUST be preserved
        retained_nums = [r.room_number for r in update_res['retained_due_to_defects']]
        self.assertIn('0910', retained_nums)
        self.assertTrue(Room.objects.filter(floor=floor, room_number='0910').exists())

    def test_safe_delete_room(self):
        """safe_delete_room refuses to delete rooms that have defect inspections."""
        res = create_floor_with_apartments(self.project, "Floor 03", Floor.FLOOR_TYPE_TYPICAL, 4)
        floor = res['floor']
        room_0301 = Room.objects.get(floor=floor, room_number='0301')
        room_0302 = Room.objects.get(floor=floor, room_number='0302')

        # Add defect to 0301
        DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            room=room_0301,
            department=DefectInspection.DEPARTMENT_ELECTRICAL,
            faults_description="Missing cable gland",
            status=DefectInspection.STATUS_PENDING
        )

        # Deleting 0301 must fail
        success, msg = safe_delete_room(room_0301)
        self.assertFalse(success)
        self.assertIn("defect inspection(s) recorded", msg)

        # Deleting 0302 (0 defects) succeeds
        success2, msg2 = safe_delete_room(room_0302)
        self.assertTrue(success2)
        self.assertFalse(Room.objects.filter(id=room_0302.id).exists())

    def test_api_floor_preview_endpoint(self):
        """Tests the AJAX preview endpoint returns correct calculated units."""
        response = self.client.get(reverse('api_floor_preview'), {
            'floor_number': 'Floor 05',
            'floor_type': 'Typical Floor',
            'apartment_count': 16,
            'starting_number': 1,
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        apts = data['preview']['apartments']
        self.assertEqual(len(apts), 16)
        self.assertEqual(apts[0], '0501')
        self.assertEqual(apts[-1], '0516')

    def test_floor_delete_requires_correct_password(self):
        """Floor deletion strictly requires the authenticated user's password."""
        res = create_floor_with_apartments(self.project, "Floor 06", Floor.FLOOR_TYPE_TYPICAL, 4)
        floor = res['floor']
        floor_id = floor.id

        # 1. Attempt with incorrect password -> MUST fail
        resp_wrong = self.client.post(reverse('floor_delete', args=[floor_id]), {
            'password': 'wrongpassword123'
        })
        self.assertEqual(resp_wrong.status_code, 302)
        self.assertTrue(Floor.objects.filter(id=floor_id).exists())

        # 2. Attempt with correct password -> MUST succeed
        resp_ok = self.client.post(reverse('floor_delete', args=[floor_id]), {
            'password': 'password123'
        })
        self.assertEqual(resp_ok.status_code, 302)
        self.assertFalse(Floor.objects.filter(id=floor_id).exists())
        self.assertEqual(Room.objects.filter(floor_id=floor_id).count(), 0)

    def test_floor_delete_with_defects_requires_confirmation(self):
        """Floor with defect inspection records requires both password and confirmation flag."""
        res = create_floor_with_apartments(self.project, "Floor 07", Floor.FLOOR_TYPE_TYPICAL, 4)
        floor = res['floor']
        room = floor.rooms.first()

        # Add defect inspection
        DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            room=room,
            department=DefectInspection.DEPARTMENT_PLUMBING,
            faults_description="PEX pipe pressure drop",
            status=DefectInspection.STATUS_NCR
        )

        # 1. Correct password but without confirm_force_delete -> MUST fail and protect data
        resp_no_confirm = self.client.post(reverse('floor_delete', args=[floor.id]), {
            'password': 'password123',
            'confirm_force_delete': '0'
        })
        self.assertEqual(resp_no_confirm.status_code, 302)
        self.assertTrue(Floor.objects.filter(id=floor.id).exists())

        # 2. Correct password AND confirm_force_delete=1 -> succeeds
        resp_confirmed = self.client.post(reverse('floor_delete', args=[floor.id]), {
            'password': 'password123',
            'confirm_force_delete': '1'
        })
        self.assertEqual(resp_confirmed.status_code, 302)
        self.assertFalse(Floor.objects.filter(id=floor.id).exists())

    def test_project_delete_requires_correct_password(self):
        """Project site deletion strictly requires the authenticated user's password."""
        # Create a disposable project
        proj = Project.objects.create(name="Site Bravo", pm_name="Eng. Mike")
        create_floor_with_apartments(proj, "Floor 01", Floor.FLOOR_TYPE_TYPICAL, 4)

        # 1. Attempt with incorrect password -> MUST fail
        resp_wrong = self.client.post(reverse('project_delete', args=[proj.id]), {
            'password': 'badpassword'
        })
        self.assertEqual(resp_wrong.status_code, 302)
        self.assertTrue(Project.objects.filter(id=proj.id).exists())

        # 2. Attempt with correct password -> MUST succeed
        resp_ok = self.client.post(reverse('project_delete', args=[proj.id]), {
            'password': 'password123'
        })
        self.assertEqual(resp_ok.status_code, 302)
        self.assertFalse(Project.objects.filter(id=proj.id).exists())

    def test_create_custom_milestone_auto_propagates_to_rooms(self):
        """Creating a new milestone (Civil/Fit-Out) automatically initializes RoomMilestoneStatus for all rooms."""
        res = create_floor_with_apartments(self.project, "Floor 15", Floor.FLOOR_TYPE_TYPICAL, 5)
        floor = res['floor']
        total_rooms = Room.objects.count()

        # Create a new Civil milestone via view
        resp = self.client.post(reverse('milestone_create'), {
            'name': 'Civil High Wall Closing',
            'category': MilestoneDefinition.CATEGORY_CIVIL,
            'description': 'Verification of blockwork and lintel closure before services containment',
            'order': 99,
            'is_active': 'on'
        })
        self.assertEqual(resp.status_code, 302)

        milestone = MilestoneDefinition.objects.get(name='Civil High Wall Closing')
        self.assertEqual(milestone.category, MilestoneDefinition.CATEGORY_CIVIL)

        # Check that RoomMilestoneStatus was automatically created for all existing rooms
        statuses = RoomMilestoneStatus.objects.filter(milestone=milestone)
        self.assertEqual(statuses.count(), total_rooms)
        for s in statuses:
            self.assertEqual(s.status, RoomMilestoneStatus.STATUS_PENDING)

    def test_image_optimization_and_webp_conversion(self):
        """Uploaded inspection images are automatically compressed and converted to WebP."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a sample large dummy JPEG in memory (2000x2000)
        img = Image.new('RGB', (2000, 2000), color=(75, 73, 172))
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG', quality=95)
        img_io.seek(0)

        uploaded = SimpleUploadedFile(
            name='site_inspection_raw.jpg',
            content=img_io.read(),
            content_type='image/jpeg'
        )

        res = create_floor_with_apartments(self.project, "Floor 20", Floor.FLOOR_TYPE_TYPICAL, 2)
        floor = res['floor']
        room = floor.rooms.first()

        inspection = DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            room=room,
            department=DefectInspection.DEPARTMENT_HVAC,
            faults_description="Test FCU leakage",
            status=DefectInspection.STATUS_PENDING,
            original_image=uploaded
        )

        # Assert that image was converted to .webp format and resized
        self.assertTrue(inspection.original_image.name.endswith('.webp'))
        # Verify saved dimensions
        saved_img = Image.open(inspection.original_image.path)
        self.assertLessEqual(max(saved_img.width, saved_img.height), 1920)
        self.assertEqual(saved_img.format, 'WEBP')

    def test_inspection_delete_requires_password(self):
        """Deleting a defect inspection strictly requires the user's login password."""
        res = create_floor_with_apartments(self.project, "Floor 25", Floor.FLOOR_TYPE_TYPICAL, 2)
        floor = res['floor']
        room = floor.rooms.first()

        insp = DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            room=room,
            department=DefectInspection.DEPARTMENT_ELECTRICAL,
            faults_description="Exposed DB cables",
            status=DefectInspection.STATUS_NCR
        )
        insp_id = insp.id

        # 1. Attempt delete with wrong password -> MUST fail
        resp_wrong = self.client.post(reverse('inspection_delete', args=[insp_id]), {
            'password': 'badpassword'
        })
        self.assertEqual(resp_wrong.status_code, 302)
        self.assertTrue(DefectInspection.objects.filter(id=insp_id).exists())

        # 2. Attempt delete with correct password -> MUST succeed
        resp_ok = self.client.post(reverse('inspection_delete', args=[insp_id]), {
            'password': 'password123'
        })
        self.assertEqual(resp_ok.status_code, 302)
        self.assertFalse(DefectInspection.objects.filter(id=insp_id).exists())

    def test_defects_gallery_view_and_filtering(self):
        """Tests the Defects Gallery view with floor, department, and date filters."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create dummy image
        img = Image.new('RGB', (100, 100), color='blue')
        img_io = io.BytesIO()
        img.save(img_io, format='JPEG')
        img_io.seek(0)
        uploaded = SimpleUploadedFile(name='defect_photo.jpg', content=img_io.read(), content_type='image/jpeg')

        res = create_floor_with_apartments(self.project, "Floor 10", Floor.FLOOR_TYPE_TYPICAL, 2)
        floor = res['floor']

        DefectInspection.objects.create(
            project=self.project,
            floor=floor,
            floor_number=10,
            department=DefectInspection.DEPARTMENT_PLUMBING,
            faults_description="PRV valve leaking water",
            status=DefectInspection.STATUS_NCR,
            original_image=uploaded
        )

        # 1. Base gallery view
        resp = self.client.get(reverse('defects_gallery'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "PRV valve leaking water")

        # 2. Filter by floor 10
        resp_floor = self.client.get(reverse('defects_gallery'), {'floor': '10'})
        self.assertEqual(resp_floor.status_code, 200)
        self.assertContains(resp_floor, "Level 10")

        # 3. Filter by department Plumbing
        resp_dept = self.client.get(reverse('defects_gallery'), {'department': 'Plumbing'})
        self.assertEqual(resp_dept.status_code, 200)
        self.assertContains(resp_dept, "Plumbing")

        # 4. Filter by date_filter today
        resp_date = self.client.get(reverse('defects_gallery'), {'date_filter': 'today'})
        self.assertEqual(resp_date.status_code, 200)
        self.assertContains(resp_date, "PRV valve leaking water")




