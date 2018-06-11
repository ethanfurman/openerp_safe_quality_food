{
   'name': 'Safe Quality Food Compliance',
    'version': '0.1',
    'category': 'Generic Modules',
    'description': """
            Repository for documents, guide lines, job descriptions,
            etc., used to maintain SQF certification.
            """,
    'author': 'Emile van Sebille',
    'maintainer': 'Emile van Sebille',
    'website': '',
    'depends': [
        'base',
	'mail',
        # 'fnx',
        # 'fis_integration',
        # 'product',
        ],
    'js': [
        ],
    'css':[
        ],
    'data': [
        'security/safe_quality_food_security.xaml',
        'security/ir.model.access.csv',
        'safe_quality_food_data.xaml',
        'safe_quality_food_view.xaml',
        ],
    'test': [],
    'installable': True,
    'active': False,
}
