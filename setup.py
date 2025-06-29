from setuptools import find_packages, setup

setup(
    name='netbox-hedgehog',
    version='0.1.0',
    description='NetBox plugin for managing Hedgehog fabric CRDs',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/hedgehog/netbox-hedgehog-plugin',
    author='Hedgehog',
    author_email='support@hedgehog.cloud',
    license='Apache 2.0',
    install_requires=[
        'kubernetes>=24.0.0',
        'pyyaml>=6.0',
        'jsonschema>=4.0.0',
    ],
    packages=find_packages(),
    include_package_data=True,
    package_data={
        'netbox_hedgehog': [
            'templates/netbox_hedgehog/*',
            'static/netbox_hedgehog/css/*',
            'static/netbox_hedgehog/js/*',
        ],
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
    python_requires='>=3.8',
    zip_safe=False,
)