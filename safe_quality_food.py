# -*- coding: utf-8 -*-

# imports
from fnx_fs.fields import files
from openerp.osv import fields, osv
from openerp.exceptions import ERPError
from fnx.oe import Normalize
import logging

_logger = logging.getLogger(__name__)

class PublicationStatus(fields.SelectionEnum):
    _order_ = 'draft submitted signed active retired cancelled'
    draft = 'Draft'
    submitted = 'Needs Signature'
    signed = 'Ready'
    active = 'Active'
    retired = 'Superceded'
    cancelled = 'Cancelled'
PS = PublicationStatus
CANCELLABLE_STATES = PS.signed, PS.active, PS.cancelled
WITHDRAWABLE_STATES = PS.signed, PS.active

# class safe_quality_food_section(osv.Model):
#     _name = 'safe_quality_food.section'
#     _inherit = []
#     _order = 'name'
#     _description = 'Safe Quality Food Section'
#
#     _columns = {
#         'name': fields.char('Section Name', size=128),
#         'file_ids': fields.one2many('safe_quality_food.file', 'section_id', string='Files'),
#         }

class safe_quality_food_document(Normalize, osv.Model):
    _name = 'safe_quality_food.document'
    _inherit = ['mail.thread', 'ir.needaction_mixin', 'fnx_fs.fs']
    _order = 'name, version desc'
    _description = 'Safe Quality Food Document'

    _fnxfs_path = 'safe_quality_food/documents'
    _fnxfs_path_fields = ['reference', 'name']

    _track = {
        'state' : {
            'safe_quality_food.mt_safe_quality_food_draft': lambda s, c, u, r, ctx: r['state'] == 'draft',
            'safe_quality_food.mt_safe_quality_food_submitted': lambda s, c, u, r, ctx: r['state'] == 'submitted',
            'safe_quality_food.mt_safe_quality_food_signed': lambda s, c, u, r, ctx: r['state'] == 'signed',
            'safe_quality_food.mt_safe_quality_food_active': lambda s, c, u, r, ctx: r['state'] == 'active',
            'safe_quality_food.mt_safe_quality_food_retired': lambda s, c, u, r, ctx: r['state'] == 'retired',
            'safe_quality_food.mt_safe_quality_food_cancelled': lambda s, c, u, r, ctx: r['state'] == 'cancelled',
            }
        }

    def _auto_init(self, cr, context=None):
        res = super(safe_quality_food_document, self)._auto_init(cr, context)
        # Use unique index to implement unique constraint on the lowercase name (not possible using a constraint)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'safe_quality_food_document_reference_name_version_unique_index'")
        if not cr.fetchone():
            cr.execute("""CREATE UNIQUE INDEX "safe_quality_food_document_reference_name_version_unique_index" ON safe_quality_food_document
                            (lower(reference), lower(name), version)""")
            cr.commit()
        return res

    def _needaction_domain_get(self, cr, uid, context=None):
        return [('signing_id','=',uid),('state','=','submitted')]

    _columns = {
        'name': fields.char('Document', size=128, required=True),
        'state': fields.selection(PS, string='Status'),
        'prev_state': fields.selection(PS, string='Previous State', help="used when uncancelling a document"),
        'reference': fields.char('Reference Number', size=64, required=True),
        'prepared_by': fields.char('Prepared By', size=128, oldname='prepared_by_id'),
        'prepared_date': fields.date('Prepared Date'),
        'approved_by': fields.char('Approved By', size=128),
        'signing_id': fields.many2one(
            'res.users',
            string='Signer',
            domain=([('groups_id','=',fields.ref('safe_quality_food.group_safe_quality_food_user'))]),
            ),
        'signed_date': fields.date('Signing Date'),
        'create_uid': fields.many2one('res.users', 'Entered By', readonly=True),
        'create_date': fields.datetime('Create Date', readonly=True),
        'effective_date': fields.date('Effective Date'),
        'supercedes': fields.date('Supercedes'),
        'superceded_by': fields.char('Superceded by', size=128),
        'version': fields.integer('Version No.', required=True),
        'sqf_edition': fields.char('SQF Edition', size=12),
        'body': fields.text('Document Body'),
        'fnxfs_files': files('', string='Extra Documents'),
        }

    _defaults = {
        'state': PS.draft,
        'version': 1,
        }

    def button_submit_for_signing(self, cr, uid, ids, context=None):
        signing_ids = [d['signing_id'][0] for d in self.read(cr, uid, ids, fields=['signing_id'])]
        self.message_subscribe_users(cr, uid, ids, user_ids=signing_ids, context=context)
        values = {
                'state': PS.submitted,
                'prepared_date': fields.date.context_today(self, cr, uid, context=context),
                }
        return self.write(cr, uid, ids, values, context=context)

    def button_sign_document(self, cr, uid, ids, context=None):
        "make document official"
        if not ids:
            return True
        if isinstance(ids, (int, long)):
            ids = [ids]
        if len(ids) > 1:
            raise ERPError('Too many records', 'Button only works for one record at a time')
        today = fields.date.context_today(self, cr, uid, context=context)
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.signing_id.id != uid:
                raise ERPError('Wrong Signee', 'Document must be signed by\n%s' % rec.signing_id.name)
            if rec.effective_date <= today:
                state = PS.active
            else:
                state = PS.signed
        result = self.write(
                cr, uid, ids,
                {'state': state, 'signed_date': today},
                context=context,
                )
        if state == PS.active:
            prev_doc_ids = self.search(
                    cr, uid,
                    [('reference','=',rec.reference),('name','=',rec.name),('version','=',rec.version-1)],
                    context=context,
                    )
            if prev_doc_ids:
                result = result and self.write(
                        cr, uid, prev_doc_ids,
                        {'state': PS.retired, 'superceded_by': rec.effective_date},
                        context=context,
                        )
        return result

    def button_edit_document(self, cr, uid, ids, context=None):
        "document needs more editing"
        if isinstance(ids, (int, long)):
            ids = [ids]
        for rec in self.browse(cr, uid, ids, context=context):
            if rec.signing_id.id != uid:
                raise ERPError('Wrong Signee', 'Function only available to\n%s' % rec.signing_id.name)
        return self.write(
                cr, uid, ids,
                {
                    'state': PS.draft,
                    },
                context=context,
                )

    def fnxfs_folder_name(self, records):
        "return name of folder to hold related files"
        res = {}
        for record in records:
            res[record['id']] = '%s-%s' % (record['reference'], record['name'])
        return res

    def menu_next_version(self, cr, uid, ids, context=None):
        "create next version of document"
        if isinstance(ids, (int, long)):
            ids = [ids]
        for doc in self.browse(cr, uid, ids, context=context):
            vals = {}
            vals['name'] = doc.name
            vals['state'] = PS.draft
            vals['reference'] = doc.reference
            vals['approved_by'] = doc.approved_by
            vals['signing_id'] = doc.signing_id.id
            vals['supercedes'] = doc.effective_date
            vals['version'] = version = doc.version + 1
            vals['body'] = doc.body
            # check to see if it already exists
            found = self.search(
                    cr, uid,
                    [('reference','=',doc.reference),('name','=',doc.name),('version','=',version)],
                    context=context)
            if found:
                raise ERPError('Duplicate Document', '%s %s version %s already exists' %
                        (doc['reference'], doc['name'], doc['version']))
            self.create(cr, uid, vals, context=context)
        return True

    def menu_withdraw(self, cr, uid, ids, context=None):
        "remove approval/signing-request from a final document, reactivate superceded document"
        if isinstance(ids, (int, long)):
            ids = [ids]
        reactivate_ids = []
        for doc in self.browse(cr, uid, ids, context=context):
            if doc.state not in WITHDRAWABLE_STATES:
                raise ERPError('Invalid Action', 'Cannot withdraw %s documents' % PS[doc.state].user)
            if doc.state == PS.active:
                reactivate_ids.extend([('reference','=',doc.reference),('name','=',doc.name),('version','=',doc.version-1)])
        self.write(cr, uid, ids, {'state': PS.draft}, context=context)
        if reactivate_ids:
            reactivate_ids = self.search(cr, uid, reactivate_ids, context=context)
            if reactivate_ids:
                self.write(cr, uid, reactivate_ids, {'state': PS.active}, context=context)
        return True

    def menu_cancel(self, cr, uid, ids, context=None):
        "cancel an approved document"
        if isinstance(ids, (int, long)):
            ids = [ids]
        signed_ids = []
        active_ids = []
        prev_signed_ids = []
        prev_active_ids = []
        for doc in self.browse(cr, uid, ids, context=context):
            print '%s-%s, ver %s: state -> %r  prev_state -> %r' % (doc.reference, doc.name, doc.version, doc.state, doc.prev_state)
            if doc.state not in CANCELLABLE_STATES:
                raise ERPError('Invalid Action', 'Cannot cancel %s documents' % PS[doc.state].user)
            if doc.state == PS.signed:
                print 'doc is signed'
                signed_ids.append(doc.id)
            elif doc.state == PS.active:
                print 'doc is active'
                active_ids.append(doc.id)
            elif doc.state == PS.cancelled and doc.prev_state == PS.signed:
                print 'doc was signed'
                prev_signed_ids.append(doc.id)
            elif doc.state == PS.cancelled and doc.prev_state == PS.active:
                print 'doc was active'
                prev_active_ids.append(doc.id)
            else:
                _logger.warning('unhandled state for "%s %s %s": %s', doc.reference, doc.name, doc.version, doc.state)
        #
        result = True
        #
        if signed_ids:
            result = result and self.write(
                    cr, uid, signed_ids,
                    {'state': PS.cancelled, 'prev_state': PS.signed},
                    context=context,
                    )
        if active_ids:
            result = result and self.write(
                    cr, uid, active_ids,
                    {'state': PS.cancelled, 'prev_state': PS.active},
                    context=context,
                    )
        if prev_signed_ids:
            result = result and self.write(
                    cr, uid, prev_signed_ids,
                    {'state': PS.signed, 'prev_state': False},
                    context=context,
                    )
        if prev_active_ids:
            result = result and self.write(
                    cr, uid, prev_active_ids,
                    {'state': PS.active, 'prev_state': False},
                    context=context,
                    )
        #
        return result

    def unlink(self, cr, uid, ids, context=None):
        # do not allow deletion of approved documents
        approved = self.search(cr, uid, [('id','in',ids),('state','!=',PS.draft)], context=context)
        if approved:
            raise ERPError('Error', 'Unable to remove approved documents')
        return super(safe_quality_food_document, self).unlink(cr, uid, ids, context=context)
