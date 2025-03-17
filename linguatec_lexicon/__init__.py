"""
Package metadata definition.
"""

VERSION = (0, 7, 0, 'final', 0)


def get_version():
    "Returns a PEP 386-compliant version number from VERSION."
    if (len(VERSION) != 5 or
            VERSION[3] not in ('alpha', 'beta', 'rc', 'final')):
        raise ValueError(
            "{} is not PEP 386-compliant version number".format(VERSION))

    # Now build the two parts of the version number:
    # main = X.Y[.Z]
    # sub = .devN - for pre-alpha releases
    #     | {a|b|c}N - for alpha, beta and rc releases

    parts = 2 if VERSION[2] == 0 else 3
    main = '.'.join(str(x) for x in VERSION[:parts])

    sub = ''

    if VERSION[3] != 'final':
        mapping = {'alpha': 'a', 'beta': 'b', 'rc': 'c'}
        sub = mapping[VERSION[3]] + str(VERSION[4])

    return str(main + sub)
