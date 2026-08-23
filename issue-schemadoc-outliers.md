# Normalise three `sd:schemaDoc` bodies that use `ddue:content` instead of `ddue:remarks`

Throughout the schema, `sd:schemaDoc` carries `ddue:summary` and `ddue:remarks`
as its direct children — 1,089 and 992 occurrences respectively. Three places
deviate and wrap their body in `ddue:content` instead. Any consumer that reads
documentation by looking for `summary` and `remarks` loses this content silently.

Measured against `develop`, commit `4beeef8`, `schema/cpacs_schema.xsd`.

## 1. `wheelType`, line 41344

```xml
<sd:schemaDoc>
    <ddue:summary>
        <ddue:para>Definition of the landing gear wheel.</ddue:para>
    </ddue:summary>
    <ddue:content>
        <ddue:para>The center plane of the wheel is located on the end point of the axle.</ddue:para>
    </ddue:content>
</sd:schemaDoc>
```

Replace `ddue:content` with `ddue:remarks`.

## 2. `elementMassType`, line 12870

Here `ddue:content` wraps a `ddue:remarks`, adding one level that exists nowhere
else — this is the only `ddue:remarks` in the schema whose parent is not
`sd:schemaDoc`.

```xml
<ddue:content>
    <ddue:remarks>
        <ddue:para>Description of the local mass properties …</ddue:para>
        …
    </ddue:remarks>
</ddue:content>
```

Drop the `ddue:content` wrapper and keep `ddue:remarks` as a direct child of
`sd:schemaDoc`.

## 3. `componentSegmentType/name`, line 7163

```xml
<xsd:element name="name" type="stringBaseType">
    <xsd:annotation>
        <xsd:appinfo>
            <sd:schemaDoc>
                <ddue:content>
                    <ddue:mediaLink>
                        <ddue:image xlink:href="axissystem"/>
                    </ddue:mediaLink>
                </ddue:content>
            </sd:schemaDoc>
        </xsd:appinfo>
        <xsd:documentation>Name of the wing componentSegment.</xsd:documentation>
    </xsd:annotation>
</xsd:element>
```

Two separate problems:

- The `ddue:content` wrapper, as above. This is also the only `sd:schemaDoc` in
  the schema without a `ddue:summary`.
- The figure `axissystem` is attached to the `name` element of
  `componentSegmentType` — that is, to the element carrying the component
  segment's name, not to the component segment itself. Whether this placement
  is intended cannot be decided from the schema; if it is not, the figure
  belongs on the owning type.

## Why fix rather than accommodate

Three occurrences against roughly two thousand regular ones. Handling them as a
special case means carrying a second code path through every documentation
consumer indefinitely. Fixing them is a change to three annotation bodies and
touches no type definition, no element name, and no instance data.

## Effect on the current Sandcastle output

Not measured. Whether the SHFB plugin renders `ddue:content` bodies, drops them,
or fails on them is unknown; the fix should be checked against the existing
build before merging.

## Reproducing

```
survey_doc_vocabulary.py schema/cpacs_schema.xsd
```

Section *structural outliers* lists all deviations with line numbers, so the
check can be repeated against any later schema state.
