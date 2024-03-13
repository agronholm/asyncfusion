import platform

from setuptools import Extension, setup

extensions = []
if platform.system() == "Linux":
    extensions.append(Extension(
        "asyncfusion._io_uring",
        extra_compile_args=["-std=c99"],
        py_limited_api=True,
        sources=["src/cextension/io_uring.c"],
        libraries=['uring'],
    ))

setup(ext_modules=extensions)
