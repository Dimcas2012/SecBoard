# SecBoard/app_risk/services/serialization_service.py

import logging
import json
import pickle
import gzip
import bz2
import lzma
import zlib
from typing import Dict, List, Optional, Any, Union, Callable, Tuple
from datetime import datetime, date
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone
from django.db import models
import msgpack

# Make orjson optional
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

from dataclasses import dataclass, asdict
from enum import Enum
import base64
import hashlib

logger = logging.getLogger(__name__)


class SerializationFormat(Enum):
    """Supported serialization formats"""
    JSON = "json"
    ORJSON = "orjson"
    PICKLE = "pickle"
    MSGPACK = "msgpack"
    BINARY = "binary"


class CompressionMethod(Enum):
    """Supported compression methods"""
    NONE = "none"
    GZIP = "gzip"
    BZ2 = "bz2"
    LZMA = "lzma"
    ZLIB = "zlib"


@dataclass
class SerializationConfig:
    """Configuration for serialization"""
    format: SerializationFormat = SerializationFormat.JSON
    compression: CompressionMethod = CompressionMethod.GZIP
    compression_level: int = 6
    include_metadata: bool = True
    optimize_for_size: bool = True
    optimize_for_speed: bool = False
    
    def validate(self):
        """Validate configuration"""
        if self.compression_level < 0 or self.compression_level > 9:
            raise ValueError("Compression level must be between 0 and 9")


class OptimizedJSONEncoder(DjangoJSONEncoder):
    """Optimized JSON encoder for Django models and complex types"""
    
    def default(self, obj):
        if isinstance(obj, models.Model):
            return self._serialize_model(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return super().default(obj)
    
    def _serialize_model(self, obj: models.Model) -> Dict[str, Any]:
        """Serialize Django model to dictionary"""
        data = {}
        
        # Get all fields
        for field in obj._meta.fields:
            value = getattr(obj, field.name)
            
            # Handle special field types
            if isinstance(field, models.DateTimeField) and value:
                data[field.name] = value.isoformat()
            elif isinstance(field, models.DecimalField) and value:
                data[field.name] = float(value)
            elif isinstance(field, models.ForeignKey) and value:
                data[field.name] = value.pk
            else:
                data[field.name] = value
        
        # Add model metadata
        data['_model'] = f"{obj._meta.app_label}.{obj._meta.model_name}"
        data['_pk'] = obj.pk
        
        return data


class SerializationService:
    """Service for optimized serialization and compression"""
    
    def __init__(self, config: SerializationConfig = None):
        self.config = config or SerializationConfig()
        self.config.validate()
        
        # Initialize serializers
        self.serializers = {
            SerializationFormat.JSON: self._serialize_json,
            SerializationFormat.ORJSON: self._serialize_orjson,
            SerializationFormat.PICKLE: self._serialize_pickle,
            SerializationFormat.MSGPACK: self._serialize_msgpack,
            SerializationFormat.BINARY: self._serialize_binary
        }
        
        # Initialize deserializers
        self.deserializers = {
            SerializationFormat.JSON: self._deserialize_json,
            SerializationFormat.ORJSON: self._deserialize_orjson,
            SerializationFormat.PICKLE: self._deserialize_pickle,
            SerializationFormat.MSGPACK: self._deserialize_msgpack,
            SerializationFormat.BINARY: self._deserialize_binary
        }
        
        # Initialize compressors
        self.compressors = {
            CompressionMethod.NONE: self._compress_none,
            CompressionMethod.GZIP: self._compress_gzip,
            CompressionMethod.BZ2: self._compress_bz2,
            CompressionMethod.LZMA: self._compress_lzma,
            CompressionMethod.ZLIB: self._compress_zlib
        }
        
        # Initialize decompressors
        self.decompressors = {
            CompressionMethod.NONE: self._decompress_none,
            CompressionMethod.GZIP: self._decompress_gzip,
            CompressionMethod.BZ2: self._decompress_bz2,
            CompressionMethod.LZMA: self._decompress_lzma,
            CompressionMethod.ZLIB: self._decompress_zlib
        }
    
    def serialize(self, data: Any, config: SerializationConfig = None) -> bytes:
        """Serialize data with compression"""
        config = config or self.config
        
        # Add metadata if enabled
        if config.include_metadata:
            data = self._add_metadata(data)
        
        # Serialize data
        serializer = self.serializers.get(config.format)
        if not serializer:
            raise ValueError(f"Unsupported serialization format: {config.format}")
        
        serialized_data = serializer(data)
        
        # Compress if needed
        compressor = self.compressors.get(config.compression)
        if not compressor:
            raise ValueError(f"Unsupported compression method: {config.compression}")
        
        compressed_data = compressor(serialized_data, config.compression_level)
        
        return compressed_data
    
    def deserialize(self, data: bytes, config: SerializationConfig = None) -> Any:
        """Deserialize compressed data"""
        config = config or self.config
        
        # Decompress if needed
        decompressor = self.decompressors.get(config.compression)
        if not decompressor:
            raise ValueError(f"Unsupported compression method: {config.compression}")
        
        decompressed_data = decompressor(data)
        
        # Deserialize data
        deserializer = self.deserializers.get(config.format)
        if not deserializer:
            raise ValueError(f"Unsupported serialization format: {config.format}")
        
        deserialized_data = deserializer(decompressed_data)
        
        # Remove metadata if present
        if config.include_metadata and isinstance(deserialized_data, dict):
            deserialized_data = self._remove_metadata(deserialized_data)
        
        return deserialized_data
    
    def _add_metadata(self, data: Any) -> Dict[str, Any]:
        """Add metadata to data"""
        if not isinstance(data, dict):
            data = {'data': data}
        
        data['_metadata'] = {
            'serialization_format': self.config.format.value,
            'compression_method': self.config.compression.value,
            'compression_level': self.config.compression_level,
            'timestamp': timezone.now().isoformat(),
            'version': '1.0'
        }
        
        return data
    
    def _remove_metadata(self, data: Dict[str, Any]) -> Any:
        """Remove metadata from data"""
        if '_metadata' in data:
            del data['_metadata']
        
        if 'data' in data and len(data) == 1:
            return data['data']
        
        return data
    
    # Serialization methods
    def _serialize_json(self, data: Any) -> bytes:
        """Serialize using JSON"""
        return json.dumps(data, cls=OptimizedJSONEncoder, ensure_ascii=False).encode('utf-8')
    
    def _serialize_orjson(self, data: Any) -> bytes:
        """Serialize using orjson (faster JSON)"""
        if not HAS_ORJSON:
            logger.warning("orjson not available, falling back to JSON")
            return self._serialize_json(data)
        
        try:
            return orjson.dumps(data, default=self._orjson_default)
        except Exception as e:
            logger.warning(f"orjson serialization failed: {e}, falling back to JSON")
            return self._serialize_json(data)
    
    def _serialize_pickle(self, data: Any) -> bytes:
        """Serialize using pickle"""
        return pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
    
    def _serialize_msgpack(self, data: Any) -> bytes:
        """Serialize using MessagePack"""
        try:
            return msgpack.packb(data, default=self._msgpack_default, use_bin_type=True)
        except ImportError:
            logger.warning("msgpack not available, falling back to pickle")
            return self._serialize_pickle(data)
    
    def _serialize_binary(self, data: Any) -> bytes:
        """Serialize using binary format (pickle)"""
        return self._serialize_pickle(data)
    
    # Deserialization methods
    def _deserialize_json(self, data: bytes) -> Any:
        """Deserialize from JSON"""
        return json.loads(data.decode('utf-8'))
    
    def _deserialize_orjson(self, data: bytes) -> Any:
        """Deserialize from orjson"""
        if not HAS_ORJSON:
            return self._deserialize_json(data)
        
        try:
            return orjson.loads(data)
        except Exception:
            return self._deserialize_json(data)
    
    def _deserialize_pickle(self, data: bytes) -> Any:
        """Deserialize from pickle"""
        return pickle.loads(data)
    
    def _deserialize_msgpack(self, data: bytes) -> Any:
        """Deserialize from MessagePack"""
        try:
            return msgpack.unpackb(data, raw=False)
        except ImportError:
            return self._deserialize_pickle(data)
    
    def _deserialize_binary(self, data: bytes) -> Any:
        """Deserialize from binary format"""
        return self._deserialize_pickle(data)
    
    # Compression methods
    def _compress_none(self, data: bytes, level: int = 0) -> bytes:
        """No compression"""
        return data
    
    def _compress_gzip(self, data: bytes, level: int = 6) -> bytes:
        """Compress using gzip"""
        return gzip.compress(data, compresslevel=level)
    
    def _compress_bz2(self, data: bytes, level: int = 6) -> bytes:
        """Compress using bz2"""
        return bz2.compress(data, compresslevel=level)
    
    def _compress_lzma(self, data: bytes, level: int = 6) -> bytes:
        """Compress using LZMA"""
        return lzma.compress(data, preset=level)
    
    def _compress_zlib(self, data: bytes, level: int = 6) -> bytes:
        """Compress using zlib"""
        return zlib.compress(data, level=level)
    
    # Decompression methods
    def _decompress_none(self, data: bytes) -> bytes:
        """No decompression"""
        return data
    
    def _decompress_gzip(self, data: bytes) -> bytes:
        """Decompress using gzip"""
        return gzip.decompress(data)
    
    def _decompress_bz2(self, data: bytes) -> bytes:
        """Decompress using bz2"""
        return bz2.decompress(data)
    
    def _decompress_lzma(self, data: bytes) -> bytes:
        """Decompress using LZMA"""
        return lzma.decompress(data)
    
    def _decompress_zlib(self, data: bytes) -> bytes:
        """Decompress using zlib"""
        return zlib.decompress(data)
    
    # Helper methods for orjson and msgpack
    def _orjson_default(self, obj):
        """Default function for orjson serialization"""
        if isinstance(obj, models.Model):
            return OptimizedJSONEncoder().default(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        else:
            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")
    
    def _msgpack_default(self, obj):
        """Default function for msgpack serialization"""
        if isinstance(obj, models.Model):
            return OptimizedJSONEncoder().default(obj)
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        else:
            return obj
    
    def get_compression_ratio(self, original_data: bytes, compressed_data: bytes) -> float:
        """Calculate compression ratio"""
        if len(original_data) == 0:
            return 1.0
        
        return len(compressed_data) / len(original_data)
    
    def benchmark_formats(self, data: Any, iterations: int = 100) -> Dict[str, Dict[str, Any]]:
        """Benchmark different serialization formats"""
        import time
        
        results = {}
        
        for format_type in SerializationFormat:
            config = SerializationConfig(
                format=format_type,
                compression=CompressionMethod.GZIP,
                compression_level=6
            )
            
            # Serialization benchmark
            start_time = time.time()
            serialized_data = None
            
            for _ in range(iterations):
                try:
                    serialized_data = self.serialize(data, config)
                except Exception as e:
                    logger.error(f"Error serializing with {format_type}: {e}")
                    break
            
            serialize_time = (time.time() - start_time) / iterations
            
            if serialized_data is None:
                continue
            
            # Deserialization benchmark
            start_time = time.time()
            
            for _ in range(iterations):
                try:
                    self.deserialize(serialized_data, config)
                except Exception as e:
                    logger.error(f"Error deserializing with {format_type}: {e}")
                    break
            
            deserialize_time = (time.time() - start_time) / iterations
            
            # Calculate original size (rough estimate)
            original_size = len(json.dumps(data, cls=OptimizedJSONEncoder).encode('utf-8'))
            
            results[format_type.value] = {
                'serialize_time': serialize_time,
                'deserialize_time': deserialize_time,
                'total_time': serialize_time + deserialize_time,
                'serialized_size': len(serialized_data),
                'original_size': original_size,
                'compression_ratio': len(serialized_data) / original_size,
                'size_reduction': (1 - len(serialized_data) / original_size) * 100
            }
        
        return results
    
    def benchmark_compression(self, data: Any, iterations: int = 100) -> Dict[str, Dict[str, Any]]:
        """Benchmark different compression methods"""
        import time
        
        # First serialize with JSON
        json_data = self._serialize_json(data)
        results = {}
        
        for compression_method in CompressionMethod:
            config = SerializationConfig(
                format=SerializationFormat.JSON,
                compression=compression_method,
                compression_level=6
            )
            
            # Compression benchmark
            start_time = time.time()
            compressed_data = None
            
            for _ in range(iterations):
                try:
                    compressor = self.compressors[compression_method]
                    compressed_data = compressor(json_data, 6)
                except Exception as e:
                    logger.error(f"Error compressing with {compression_method}: {e}")
                    break
            
            compress_time = (time.time() - start_time) / iterations
            
            if compressed_data is None:
                continue
            
            # Decompression benchmark
            start_time = time.time()
            
            for _ in range(iterations):
                try:
                    decompressor = self.decompressors[compression_method]
                    decompressor(compressed_data)
                except Exception as e:
                    logger.error(f"Error decompressing with {compression_method}: {e}")
                    break
            
            decompress_time = (time.time() - start_time) / iterations
            
            results[compression_method.value] = {
                'compress_time': compress_time,
                'decompress_time': decompress_time,
                'total_time': compress_time + decompress_time,
                'compressed_size': len(compressed_data),
                'original_size': len(json_data),
                'compression_ratio': len(compressed_data) / len(json_data),
                'size_reduction': (1 - len(compressed_data) / len(json_data)) * 100
            }
        
        return results
    
    def optimize_config_for_data(self, data: Any) -> SerializationConfig:
        """Optimize configuration based on data characteristics"""
        # Benchmark different configurations
        format_results = self.benchmark_formats(data, iterations=10)
        compression_results = self.benchmark_compression(data, iterations=10)
        
        # Choose best format based on criteria
        best_format = SerializationFormat.JSON
        best_compression = CompressionMethod.GZIP
        
        if self.config.optimize_for_size:
            # Choose format with best compression ratio
            best_format_result = min(format_results.items(), 
                                   key=lambda x: x[1]['compression_ratio'])
            best_format = SerializationFormat(best_format_result[0])
            
            # Choose compression with best ratio
            best_compression_result = min(compression_results.items(),
                                        key=lambda x: x[1]['compression_ratio'])
            best_compression = CompressionMethod(best_compression_result[0])
        
        elif self.config.optimize_for_speed:
            # Choose format with best speed
            best_format_result = min(format_results.items(),
                                   key=lambda x: x[1]['total_time'])
            best_format = SerializationFormat(best_format_result[0])
            
            # Choose compression with best speed
            best_compression_result = min(compression_results.items(),
                                        key=lambda x: x[1]['total_time'])
            best_compression = CompressionMethod(best_compression_result[0])
        
        return SerializationConfig(
            format=best_format,
            compression=best_compression,
            compression_level=6,
            include_metadata=self.config.include_metadata
        )


class ReportSerializationService:
    """Specialized serialization service for reports"""
    
    def __init__(self):
        self.serialization_service = SerializationService()
        self.report_configs = {
            'small': SerializationConfig(
                format=SerializationFormat.JSON,
                compression=CompressionMethod.GZIP,
                compression_level=6
            ),
            'medium': SerializationConfig(
                format=SerializationFormat.MSGPACK,
                compression=CompressionMethod.GZIP,
                compression_level=6
            ),
            'large': SerializationConfig(
                format=SerializationFormat.PICKLE,
                compression=CompressionMethod.LZMA,
                compression_level=6
            )
        }
    
    def serialize_report_data(self, report_data: Dict[str, Any], 
                            size_category: str = 'medium') -> bytes:
        """Serialize report data with optimal configuration"""
        config = self.report_configs.get(size_category, self.report_configs['medium'])
        
        # Optimize data before serialization
        optimized_data = self._optimize_report_data(report_data)
        
        return self.serialization_service.serialize(optimized_data, config)
    
    def deserialize_report_data(self, serialized_data: bytes,
                              size_category: str = 'medium') -> Dict[str, Any]:
        """Deserialize report data"""
        config = self.report_configs.get(size_category, self.report_configs['medium'])
        
        return self.serialization_service.deserialize(serialized_data, config)
    
    def _optimize_report_data(self, report_data: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize report data for serialization"""
        optimized_data = {}
        
        for key, value in report_data.items():
            if key == 'assets' and isinstance(value, list):
                # Optimize assets data
                optimized_data[key] = self._optimize_assets_data(value)
            elif key == 'statistics' and isinstance(value, dict):
                # Optimize statistics data
                optimized_data[key] = self._optimize_statistics_data(value)
            elif key == 'user' and hasattr(value, '_meta'):
                # Serialize user as minimal data
                optimized_data[key] = {
                    'id': value.id,
                    'username': value.username,
                    'full_name': value.get_full_name()
                }
            else:
                optimized_data[key] = value
        
        return optimized_data
    
    def _optimize_assets_data(self, assets: List[Any]) -> List[Dict[str, Any]]:
        """Optimize assets data for serialization"""
        optimized_assets = []
        
        for asset in assets:
            if hasattr(asset, '_meta'):
                # Django model - serialize only necessary fields
                optimized_asset = {
                    'id': asset.id,
                    'name': asset.name,
                    'company_id': asset.company_id if hasattr(asset, 'company_id') else None,
                    'criticality': asset.criticality.name if hasattr(asset, 'criticality') and asset.criticality else None,
                    'vulnerability_count': getattr(asset, 'vulnerability_count', 0),
                    'high_risk_count': getattr(asset, 'high_risk_count', 0),
                    'treatment_count': getattr(asset, 'treatment_count', 0)
                }
                optimized_assets.append(optimized_asset)
            else:
                optimized_assets.append(asset)
        
        return optimized_assets
    
    def _optimize_statistics_data(self, statistics: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize statistics data for serialization"""
        # Round floating point numbers to reduce size
        optimized_stats = {}
        
        for key, value in statistics.items():
            if isinstance(value, float):
                optimized_stats[key] = round(value, 2)
            elif isinstance(value, Decimal):
                optimized_stats[key] = round(float(value), 2)
            else:
                optimized_stats[key] = value
        
        return optimized_stats
    
    def estimate_serialization_size(self, report_data: Dict[str, Any]) -> Dict[str, int]:
        """Estimate serialization size for different configurations"""
        sizes = {}
        
        for category, config in self.report_configs.items():
            try:
                serialized = self.serialization_service.serialize(report_data, config)
                sizes[category] = len(serialized)
            except Exception as e:
                logger.error(f"Error estimating size for {category}: {e}")
                sizes[category] = 0
        
        return sizes


# Global serialization service instance
serialization_service = SerializationService()
report_serialization_service = ReportSerializationService()


def get_serialization_service() -> SerializationService:
    """Get global serialization service instance"""
    return serialization_service


def get_report_serialization_service() -> ReportSerializationService:
    """Get global report serialization service instance"""
    return report_serialization_service