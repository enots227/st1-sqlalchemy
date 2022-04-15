from setuptools import find_packages, setup


def readme():
    with open('README.md') as f:
        return f.read()


setup(
    name='st1-sqlalchemy',
    version='0.0.1',
    description='A package for managing multiple SQLAlchemy databases.',
    author='Stone Sommers',
    author_email='enots227@gmail.com',
    include_package_data=True,
    packages=find_packages(
        exclude=['tests.*', 'tests']
    ),
    install_requires=[
        'SQLAlchemy>=1.4.31'
    ]
)

