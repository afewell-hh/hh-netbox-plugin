import json
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class CRDSchemaManager:
    """
    Manages CRD schemas and provides validation and form generation capabilities.
    Contains schema definitions for all supported Hedgehog CRDs.
    """
    
    # VPC API CRD Schemas
    VPC_SCHEMA = {
        "type": "object",
        "properties": {
            "ipv4Namespace": {
                "type": "string",
                "description": "IPv4 namespace for this VPC",
                "default": "default"
            },
            "vlanNamespace": {
                "type": "string", 
                "description": "VLAN namespace for this VPC",
                "default": "default"
            },
            "subnets": {
                "type": "object",
                "additionalProperties": {
                    "type": "object",
                    "properties": {
                        "subnet": {
                            "type": "string",
                            "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$",
                            "description": "CIDR subnet notation"
                        },
                        "gateway": {
                            "type": "string",
                            "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}$",
                            "description": "Gateway IP address"
                        },
                        "dhcp": {
                            "type": "object",
                            "properties": {
                                "enable": {"type": "boolean"},
                                "start": {"type": "string"},
                                "end": {"type": "string"}
                            }
                        }
                    },
                    "required": ["subnet"]
                }
            },
            "permit": {
                "type": "object",
                "properties": {
                    "vpcPeering": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "externalPeering": {
                        "type": "array", 
                        "items": {"type": "string"}
                    }
                }
            }
        },
        "required": ["ipv4Namespace", "subnets"]
    }
    
    EXTERNAL_SCHEMA = {
        "type": "object",
        "properties": {
            "ipv4Namespace": {
                "type": "string",
                "description": "IPv4 namespace for external system"
            },
            "inboundCommunity": {
                "type": "string",
                "description": "BGP community for inbound routes"
            },
            "outboundCommunity": {
                "type": "string",
                "description": "BGP community for outbound routes"
            }
        },
        "required": ["ipv4Namespace"]
    }
    
    IPV4_NAMESPACE_SCHEMA = {
        "type": "object", 
        "properties": {
            "subnets": {
                "type": "array",
                "items": {
                    "type": "string",
                    "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$"
                },
                "description": "List of CIDR subnets"
            }
        },
        "required": ["subnets"]
    }
    
    # Wiring API CRD Schemas
    CONNECTION_SCHEMA = {
        "type": "object",
        "oneOf": [
            {
                "properties": {
                    "unbundled": {
                        "type": "object",
                        "properties": {
                            "link": {
                                "type": "object",
                                "properties": {
                                    "server": {
                                        "type": "object",
                                        "properties": {
                                            "port": {"type": "string"}
                                        },
                                        "required": ["port"]
                                    },
                                    "switch": {
                                        "type": "object",
                                        "properties": {
                                            "port": {"type": "string"}
                                        },
                                        "required": ["port"]
                                    }
                                },
                                "required": ["server", "switch"]
                            }
                        },
                        "required": ["link"]
                    }
                },
                "required": ["unbundled"]
            },
            {
                "properties": {
                    "bundled": {
                        "type": "object",
                        "properties": {
                            "links": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "server": {
                                            "type": "object",
                                            "properties": {
                                                "port": {"type": "string"}
                                            },
                                            "required": ["port"]
                                        },
                                        "switch": {
                                            "type": "object", 
                                            "properties": {
                                                "port": {"type": "string"}
                                            },
                                            "required": ["port"]
                                        }
                                    },
                                    "required": ["server", "switch"]
                                }
                            }
                        },
                        "required": ["links"]
                    }
                },
                "required": ["bundled"]
            },
            {
                "properties": {
                    "fabric": {
                        "type": "object",
                        "properties": {
                            "links": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "spine": {
                                            "type": "object",
                                            "properties": {
                                                "port": {"type": "string"},
                                                "ip": {"type": "string"}
                                            },
                                            "required": ["port", "ip"]
                                        },
                                        "leaf": {
                                            "type": "object",
                                            "properties": {
                                                "port": {"type": "string"},
                                                "ip": {"type": "string"}
                                            },
                                            "required": ["port", "ip"]
                                        }
                                    },
                                    "required": ["spine", "leaf"]
                                }
                            }
                        },
                        "required": ["links"]
                    }
                },
                "required": ["fabric"]
            }
        ]
    }
    
    SWITCH_SCHEMA = {
        "type": "object",
        "properties": {
            "role": {
                "type": "string",
                "enum": ["spine", "server-leaf", "border", "leaf"],
                "description": "Switch role in fabric"
            },
            "asn": {
                "type": "integer",
                "minimum": 1,
                "maximum": 4294967295,
                "description": "BGP ASN for this switch"
            },
            "profile": {
                "type": "string",
                "description": "Switch profile name"
            },
            "description": {
                "type": "string",
                "description": "Switch description"
            },
            "ip": {
                "type": "string",
                "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$",
                "description": "Management IP address with CIDR"
            },
            "protocolIP": {
                "type": "string",
                "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$",
                "description": "Protocol IP address with CIDR"
            },
            "vtepIP": {
                "type": "string",
                "pattern": "^([0-9]{1,3}\\.){3}[0-9]{1,3}/[0-9]{1,2}$",
                "description": "VTEP IP address with CIDR"
            },
            "redundancy": {
                "type": "object",
                "properties": {
                    "group": {"type": "string"},
                    "type": {
                        "type": "string", 
                        "enum": ["mclag", "eslag"]
                    }
                }
            },
            "groups": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Switch groups this switch belongs to"
            },
            "vlanNamespaces": {
                "type": "array",
                "items": {"type": "string"},
                "description": "VLAN namespaces available on this switch"
            },
            "boot": {
                "type": "object",
                "properties": {
                    "mac": {
                        "type": "string",
                        "pattern": "^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$",
                        "description": "Boot MAC address"
                    }
                }
            }
        },
        "required": ["role"]
    }
    
    SERVER_SCHEMA = {
        "type": "object",
        "properties": {
            "description": {
                "type": "string",
                "description": "Server description"
            }
        }
    }
    
    VLAN_NAMESPACE_SCHEMA = {
        "type": "object",
        "properties": {
            "ranges": {
                "type": "array", 
                "items": {
                    "type": "object",
                    "properties": {
                        "from": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 4094,
                            "description": "Starting VLAN ID"
                        },
                        "to": {
                            "type": "integer", 
                            "minimum": 1,
                            "maximum": 4094,
                            "description": "Ending VLAN ID"
                        }
                    },
                    "required": ["from", "to"]
                },
                "description": "VLAN ID ranges"
            }
        },
        "required": ["ranges"]
    }
    
    # Map CRD types to schemas
    SCHEMAS = {
        'vpc': VPC_SCHEMA,
        'external': EXTERNAL_SCHEMA,
        'ipv4namespace': IPV4_NAMESPACE_SCHEMA,
        'connection': CONNECTION_SCHEMA,
        'switch': SWITCH_SCHEMA,
        'server': SERVER_SCHEMA,
        'vlannamespace': VLAN_NAMESPACE_SCHEMA,
    }
    
    @classmethod
    def get_schema(cls, crd_type: str) -> Optional[Dict[str, Any]]:
        """Get JSON schema for a CRD type"""
        return cls.SCHEMAS.get(crd_type.lower())
    
    @classmethod
    def validate_spec(cls, crd_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate CRD spec against schema.
        Returns validation result with errors if any.
        """
        try:
            import jsonschema
        except ImportError:
            return {
                'valid': True,
                'warning': 'jsonschema not available, skipping validation'
            }
        
        schema = cls.get_schema(crd_type)
        if not schema:
            return {
                'valid': True,
                'warning': f'No schema available for CRD type: {crd_type}'
            }
        
        try:
            jsonschema.validate(spec, schema)
            return {'valid': True}
        except jsonschema.ValidationError as e:
            return {
                'valid': False,
                'error': str(e),
                'path': list(e.absolute_path) if e.absolute_path else []
            }
        except Exception as e:
            return {
                'valid': False,
                'error': f'Validation error: {str(e)}'
            }
    
    @classmethod
    def get_example_spec(cls, crd_type: str) -> Optional[Dict[str, Any]]:
        """Get example specification for a CRD type"""
        examples = {
            'vpc': {
                "ipv4Namespace": "default",
                "subnets": {
                    "default": {
                        "subnet": "10.10.1.0/24",
                        "gateway": "10.10.1.1",
                        "dhcp": {
                            "enable": True,
                            "start": "10.10.1.10",
                            "end": "10.10.1.200"
                        }
                    }
                }
            },
            'external': {
                "ipv4Namespace": "default",
                "inboundCommunity": "65100:100",
                "outboundCommunity": "65100:200"
            },
            'ipv4namespace': {
                "subnets": [
                    "10.10.0.0/16",
                    "172.16.0.0/12"
                ]
            },
            'connection': {
                "unbundled": {
                    "link": {
                        "server": {
                            "port": "server-01/eth0"
                        },
                        "switch": {
                            "port": "leaf-01/Ethernet1"
                        }
                    }
                }
            },
            'switch': {
                "role": "leaf",
                "asn": 65001,
                "vlanNamespaces": ["default"],
                "portGroups": {
                    "downlinks": {
                        "speed": "25G",
                        "ports": ["Ethernet1", "Ethernet2"]
                    }
                }
            },
            'server': {
                "description": "Application server"
            },
            'vlannamespace': {
                "ranges": [
                    {
                        "start": 100,
                        "end": 200
                    }
                ]
            }
        }
        
        return examples.get(crd_type.lower())
    
    @classmethod
    def get_form_fields(cls, crd_type: str) -> List[Dict[str, Any]]:
        """
        Generate form field definitions from schema.
        Returns list of field definitions for UI generation.
        """
        schema = cls.get_schema(crd_type)
        if not schema:
            return []
        
        def extract_fields(properties: Dict[str, Any], path: str = "") -> List[Dict[str, Any]]:
            fields = []
            
            for field_name, field_schema in properties.items():
                field_path = f"{path}.{field_name}" if path else field_name
                field_type = field_schema.get('type', 'string')
                
                field_def = {
                    'name': field_name,
                    'path': field_path,
                    'type': field_type,
                    'description': field_schema.get('description', ''),
                    'required': field_name in schema.get('required', [])
                }
                
                # Add type-specific properties
                if field_type == 'string':
                    if 'enum' in field_schema:
                        field_def['choices'] = field_schema['enum']
                    if 'pattern' in field_schema:
                        field_def['pattern'] = field_schema['pattern']
                
                elif field_type == 'integer':
                    field_def['minimum'] = field_schema.get('minimum')
                    field_def['maximum'] = field_schema.get('maximum')
                
                elif field_type == 'object':
                    if 'properties' in field_schema:
                        field_def['children'] = extract_fields(
                            field_schema['properties'], field_path
                        )
                
                elif field_type == 'array':
                    items_schema = field_schema.get('items', {})
                    if items_schema.get('type') == 'object' and 'properties' in items_schema:
                        field_def['item_fields'] = extract_fields(
                            items_schema['properties'], f"{field_path}[]"
                        )
                
                fields.append(field_def)
            
            return fields
        
        if 'properties' in schema:
            return extract_fields(schema['properties'])
        
        return []