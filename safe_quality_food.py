# -*- coding: utf-8 -*-

# imports
from openerp.osv import fields, osv
from openerp.exceptions import ERPError
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

class safe_quality_food_document(osv.Model):
    _name = 'safe_quality_food.document'
    _inherit = ['mail.thread', 'ir.needaction_mixin']
    _order = 'name, version desc'
    _description = 'Safe Quality Food Document'

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
        super(safe_quality_food_document, self)._auto_init(cr, context)
        # Use unique index to implement unique constraint on the lowercase name (not possible using a constraint)
        cr.execute("SELECT indexname FROM pg_indexes WHERE indexname = 'safe_quality_food_document_reference_name_version_unique_index'")
        if not cr.fetchone():
            cr.execute("""CREATE UNIQUE INDEX "safe_quality_food_document_reference_name_version_unique_index" ON safe_quality_food_document
                            (lower(reference), lower(name), version)""")
            cr.commit()

    def _needaction_domain_get(self, cr, uid, context=None):
        return [('signing_id','=',uid),('state','=','submitted')]

    _columns = {
        'name': fields.char('Document', size=128, required=True),
        'state': fields.selection(PublicationStatus, string='Status'),
        'reference': fields.char('Reference Number', size=64, required=True),
        'prepared_by_id': fields.many2one('res.users', 'Prepared By'),
        'prepared_date': fields.date('Prepared Date'),
        'approved_by': fields.char('Approved By', size=128),
        'signing_id': fields.many2one('res.users', 'Signer'),
        'signed_date': fields.date('Signing Date'),
        'create_uid': fields.many2one('res.users', 'Entered By', readonly=True),
        'create_date': fields.datetime('Create Date', readonly=True),
        'effective_date': fields.date('Effective Date'),
        'supercedes': fields.date('Supercedes'),
        'superceded_by': fields.char('Superceded by', size=128),
        'version': fields.integer('Version No.', required=True),
        'sqf_edition': fields.char('SQF Edition', size=12),
        'body': fields.text('Document Body'),
        }

    _defaults = {
        'state': PublicationStatus.draft,
        'version': 1,
        }

    def button_submit_for_signing(self, cr, uid, ids, context=None):
        signing_ids = [d['signing_id'][0] for d in self.read(cr, uid, ids, fields=['signing_id'])]
        self.message_subscribe_users(cr, uid, ids, user_ids=signing_ids, context=context)
        values = {
                'state': PublicationStatus.submitted,
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
                state = PublicationStatus.active
            else:
                state = PublicationStatus.signed
        return self.write(
                cr, uid, ids,
                {
                    'state': state,
                    'signed_date': today,
                    },
                context=context,
                )

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
                    'state': PublicationStatus.draft,
                    },
                context=context,
                )

    def menu_next_version(self, cr, uid, ids, context=None):
        if isinstance(ids, (int, long)):
            ids = [ids]
        for doc in self.browse(cr, uid, ids, context=context):
            vals = {}
            vals['name'] = doc.name
            vals['state'] = PublicationStatus.draft
            vals['reference'] = doc.reference
            vals['approved_by'] = doc.approved_by
            vals['signing_id'] = doc.signing_id.id
            vals['supercedes'] = doc.effective_date
            vals['version'] = doc.version + 1
            vals['body'] = doc.body
            # check to see if it already exists
            found = self.search(
                    cr, uid,
                    [('reference','=',doc.reference),('name','=',doc.name),('version','=',doc.version)],
                    context=context)
            if found:
                raise ERPError('Duplicate Document', '%s %s version %s already exists' %
                        (doc['reference'], doc['name'], doc['version']))
            self.create(cr, uid, vals, context=context)
        return True
