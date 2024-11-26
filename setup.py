from setuptools import setup


setup(
    name='cldfbench_bonmannsymmetrical',
    py_modules=['cldfbench_bonmannsymmetrical'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'cldfbench.dataset': [
            'bonmannsymmetrical=cldfbench_bonmannsymmetrical:Dataset',
        ]
    },
    install_requires=[
        'cldfbench[glottolog]',
    ],
    extras_require={
        'test': [
            'pytest-cldf',
        ],
    },
)
