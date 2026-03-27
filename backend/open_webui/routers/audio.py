import hashlib
import json
import logging
import os
import uuid
from pydub import AudioSegment
from pydub.silence import split_on_silence
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import (
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
    APIRouter,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel


from open_webui.utils.misc import strict_match_mime_type
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.access_control import has_permission
from open_webui.config import (
    WHISPER_MODEL_AUTO_UPDATE,
    WHISPER_COMPUTE_TYPE,
    WHISPER_MODEL_DIR,
    WHISPER_VAD_FILTER,
    CACHE_DIR,
    WHISPER_LANGUAGE,
    WHISPER_MULTILINGUAL,
)

from open_webui.constants import ERROR_MESSAGES
from open_webui.env import (
    DEVICE_TYPE,
)

router = APIRouter()

# Constants
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert MB to bytes

log = logging.getLogger(__name__)

SPEECH_CACHE_DIR = CACHE_DIR / 'audio' / 'speech'
SPEECH_CACHE_DIR.mkdir(parents=True, exist_ok=True)


##########################################
#
# Utility functions
#
##########################################

from pydub import AudioSegment
from pydub.utils import mediainfo


def is_audio_conversion_required(file_path):
    """
    Check if the given audio file needs conversion to mp3.
    """
    SUPPORTED_FORMATS = {'flac', 'm4a', 'mp3', 'mp4', 'mpeg', 'wav', 'webm'}

    if not os.path.isfile(file_path):
        log.error(f'File not found: {file_path}')
        return False

    try:
        info = mediainfo(file_path)
        codec_name = info.get('codec_name', '').lower()
        codec_type = info.get('codec_type', '').lower()
        codec_tag_string = info.get('codec_tag_string', '').lower()

        if codec_name == 'aac' and codec_type == 'audio' and codec_tag_string == 'mp4a':
            # File is AAC/mp4a audio, recommend mp3 conversion
            return True

        # If the codec name is in the supported formats
        if codec_name in SUPPORTED_FORMATS:
            return False

        return True
    except Exception as e:
        log.error(f'Error getting audio format: {e}')
        return False


def convert_audio_to_mp3(file_path):
    """Convert audio file to mp3 format."""
    try:
        output_path = os.path.splitext(file_path)[0] + '.mp3'
        audio = AudioSegment.from_file(file_path)
        audio.export(output_path, format='mp3')
        log.info(f'Converted {file_path} to {output_path}')
        return output_path
    except Exception as e:
        log.error(f'Error converting audio file: {e}')
        return None


def set_faster_whisper_model(model: str, auto_update: bool = False):
    whisper_model = None
    if model:
        from faster_whisper import WhisperModel

        faster_whisper_kwargs = {
            'model_size_or_path': model,
            'device': DEVICE_TYPE if DEVICE_TYPE and DEVICE_TYPE == 'cuda' else 'cpu',
            'compute_type': WHISPER_COMPUTE_TYPE,
            'download_root': WHISPER_MODEL_DIR,
            'local_files_only': not auto_update,
        }

        try:
            whisper_model = WhisperModel(**faster_whisper_kwargs)
        except Exception:
            log.warning('WhisperModel initialization failed, attempting download with local_files_only=False')
            faster_whisper_kwargs['local_files_only'] = False
            whisper_model = WhisperModel(**faster_whisper_kwargs)
    return whisper_model


##########################################
#
# Audio API
#
##########################################


class TTSConfigForm(BaseModel):
    ENGINE: str
    MODEL: str
    VOICE: str
    SPLIT_ON: str


class STTConfigForm(BaseModel):
    ENGINE: str
    MODEL: str
    SUPPORTED_CONTENT_TYPES: list[str] = []
    WHISPER_MODEL: str


class AudioConfigUpdateForm(BaseModel):
    tts: TTSConfigForm
    stt: STTConfigForm


@router.get('/config')
async def get_audio_config(request: Request, user=Depends(get_admin_user)):
    return {
        'tts': {
            'ENGINE': request.app.state.config.TTS_ENGINE,
            'MODEL': request.app.state.config.TTS_MODEL,
            'VOICE': request.app.state.config.TTS_VOICE,
            'SPLIT_ON': request.app.state.config.TTS_SPLIT_ON,
        },
        'stt': {
            'ENGINE': request.app.state.config.STT_ENGINE,
            'MODEL': request.app.state.config.STT_MODEL,
            'SUPPORTED_CONTENT_TYPES': request.app.state.config.STT_SUPPORTED_CONTENT_TYPES,
            'WHISPER_MODEL': request.app.state.config.WHISPER_MODEL,
        },
    }


@router.post('/config/update')
async def update_audio_config(request: Request, form_data: AudioConfigUpdateForm, user=Depends(get_admin_user)):
    request.app.state.config.TTS_ENGINE = form_data.tts.ENGINE
    request.app.state.config.TTS_MODEL = form_data.tts.MODEL
    request.app.state.config.TTS_VOICE = form_data.tts.VOICE
    request.app.state.config.TTS_SPLIT_ON = form_data.tts.SPLIT_ON

    request.app.state.config.STT_ENGINE = form_data.stt.ENGINE
    request.app.state.config.STT_MODEL = form_data.stt.MODEL
    request.app.state.config.STT_SUPPORTED_CONTENT_TYPES = form_data.stt.SUPPORTED_CONTENT_TYPES

    request.app.state.config.WHISPER_MODEL = form_data.stt.WHISPER_MODEL

    if request.app.state.config.STT_ENGINE == '':
        request.app.state.faster_whisper_model = set_faster_whisper_model(
            form_data.stt.WHISPER_MODEL, WHISPER_MODEL_AUTO_UPDATE
        )
    else:
        request.app.state.faster_whisper_model = None

    return {
        'tts': {
            'ENGINE': request.app.state.config.TTS_ENGINE,
            'MODEL': request.app.state.config.TTS_MODEL,
            'VOICE': request.app.state.config.TTS_VOICE,
            'SPLIT_ON': request.app.state.config.TTS_SPLIT_ON,
        },
        'stt': {
            'ENGINE': request.app.state.config.STT_ENGINE,
            'MODEL': request.app.state.config.STT_MODEL,
            'SUPPORTED_CONTENT_TYPES': request.app.state.config.STT_SUPPORTED_CONTENT_TYPES,
            'WHISPER_MODEL': request.app.state.config.WHISPER_MODEL,
        },
    }


def load_speech_pipeline(request):
    from transformers import pipeline
    from datasets import load_dataset

    if request.app.state.speech_synthesiser is None:
        request.app.state.speech_synthesiser = pipeline('text-to-speech', 'microsoft/speecht5_tts')

    if request.app.state.speech_speaker_embeddings_dataset is None:
        request.app.state.speech_speaker_embeddings_dataset = load_dataset(
            'Matthijs/cmu-arctic-xvectors', split='validation'
        )


@router.post('/speech')
async def speech(request: Request, user=Depends(get_verified_user)):
    if request.app.state.config.TTS_ENGINE == '':
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=ERROR_MESSAGES.NOT_FOUND,
        )

    if user.role != 'admin' and not has_permission(user.id, 'chat.tts', request.app.state.config.USER_PERMISSIONS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )

    body = await request.body()
    name = hashlib.sha256(
        body
        + str(request.app.state.config.TTS_ENGINE).encode('utf-8')
        + str(request.app.state.config.TTS_MODEL).encode('utf-8')
    ).hexdigest()

    file_path = SPEECH_CACHE_DIR.joinpath(f'{name}.mp3')
    file_body_path = SPEECH_CACHE_DIR.joinpath(f'{name}.json')

    # Check if the file already exists in the cache
    if file_path.is_file():
        return FileResponse(file_path)

    payload = None
    try:
        payload = json.loads(body.decode('utf-8'))
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail='Invalid JSON payload')

    if request.app.state.config.TTS_ENGINE == 'transformers':
        import torch
        import soundfile as sf

        load_speech_pipeline(request)

        embeddings_dataset = request.app.state.speech_speaker_embeddings_dataset

        speaker_index = 6799
        try:
            speaker_index = embeddings_dataset['filename'].index(request.app.state.config.TTS_MODEL)
        except Exception:
            pass

        speaker_embedding = torch.tensor(embeddings_dataset[speaker_index]['xvector']).unsqueeze(0)

        speech_output = request.app.state.speech_synthesiser(
            payload['input'],
            forward_params={'speaker_embeddings': speaker_embedding},
        )

        sf.write(file_path, speech_output['audio'], samplerate=speech_output['sampling_rate'])

        async with __import__('aiofiles').open(file_body_path, 'w') as f:
            await f.write(json.dumps(payload))

        return FileResponse(file_path)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Unsupported TTS engine. Only "transformers" is available in offline mode.',
    )


def transcription_handler(request, file_path, metadata, user=None):
    filename = os.path.basename(file_path)
    file_dir = os.path.dirname(file_path)
    id = filename.split('.')[0]

    metadata = metadata or {}

    languages = [
        metadata.get('language', None) if not WHISPER_LANGUAGE else WHISPER_LANGUAGE,
        None,  # Always fallback to None in case transcription fails
    ]

    if request.app.state.config.STT_ENGINE in ('', 'whisper'):
        if request.app.state.faster_whisper_model is None:
            request.app.state.faster_whisper_model = set_faster_whisper_model(request.app.state.config.WHISPER_MODEL)

        model = request.app.state.faster_whisper_model
        segments, info = model.transcribe(
            file_path,
            beam_size=5,
            vad_filter=WHISPER_VAD_FILTER,
            language=languages[0],
            multilingual=WHISPER_MULTILINGUAL,
        )
        log.info("Detected language '%s' with probability %f" % (info.language, info.language_probability))

        transcript = ''.join([segment.text for segment in list(segments)])
        data = {'text': transcript.strip()}

        # save the transcript to a json file
        transcript_file = f'{file_dir}/{id}.json'
        with open(transcript_file, 'w') as f:
            json.dump(data, f)

        log.debug(data)
        return data

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail='Unsupported STT engine. Only local Whisper ("" or "whisper") and "web" are available in offline mode.',
    )


def transcribe(request: Request, file_path: str, metadata: Optional[dict] = None, user=None):
    log.info(f'transcribe: {file_path} {metadata}')

    if is_audio_conversion_required(file_path):
        file_path = convert_audio_to_mp3(file_path)

    try:
        file_path = compress_audio(file_path)
    except Exception as e:
        log.exception(e)

    # Always produce a list of chunk paths (could be one entry if small)
    try:
        chunk_paths = split_audio(file_path, MAX_FILE_SIZE)
        print(f'Chunk paths: {chunk_paths}')
    except Exception as e:
        log.exception(e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DEFAULT(e),
        )

    results = []
    try:
        with ThreadPoolExecutor() as executor:
            # Submit tasks for each chunk_path
            futures = [
                executor.submit(transcription_handler, request, chunk_path, metadata, user)
                for chunk_path in chunk_paths
            ]
            # Gather results as they complete
            for future in futures:
                try:
                    results.append(future.result())
                except HTTPException:
                    raise
                except Exception as transcribe_exc:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f'Error transcribing chunk: {transcribe_exc}',
                    )
    finally:
        # Clean up only the temporary chunks, never the original file
        for chunk_path in chunk_paths:
            if chunk_path != file_path and os.path.isfile(chunk_path):
                try:
                    os.remove(chunk_path)
                except Exception:
                    pass

    return {
        'text': ' '.join([result['text'] for result in results]),
    }


def compress_audio(file_path):
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        id = os.path.splitext(os.path.basename(file_path))[0]  # Handles names with multiple dots
        file_dir = os.path.dirname(file_path)

        audio = AudioSegment.from_file(file_path)
        audio = audio.set_frame_rate(16000).set_channels(1)  # Compress audio

        compressed_path = os.path.join(file_dir, f'{id}_compressed.mp3')
        audio.export(compressed_path, format='mp3', bitrate='32k')

        return compressed_path
    else:
        return file_path


def split_audio(file_path, max_bytes, format='mp3', bitrate='32k'):
    """
    Splits audio into chunks not exceeding max_bytes.
    Returns a list of chunk file paths. If audio fits, returns list with original path.
    """
    file_size = os.path.getsize(file_path)
    if file_size <= max_bytes:
        return [file_path]  # Nothing to split

    audio = AudioSegment.from_file(file_path)
    duration_ms = len(audio)
    orig_size = file_size

    approx_chunk_ms = max(int(duration_ms * (max_bytes / orig_size)) - 1000, 1000)
    chunks = []
    start = 0
    i = 0

    base, _ = os.path.splitext(file_path)

    while start < duration_ms:
        end = min(start + approx_chunk_ms, duration_ms)
        chunk = audio[start:end]
        chunk_path = f'{base}_chunk_{i}.{format}'
        chunk.export(chunk_path, format=format, bitrate=bitrate)

        # Reduce chunk duration if still too large
        while os.path.getsize(chunk_path) > max_bytes and (end - start) > 5000:
            end = start + ((end - start) // 2)
            chunk = audio[start:end]
            chunk.export(chunk_path, format=format, bitrate=bitrate)

        if os.path.getsize(chunk_path) > max_bytes:
            os.remove(chunk_path)
            raise Exception('Audio chunk cannot be reduced below max file size.')

        chunks.append(chunk_path)
        start = end
        i += 1

    return chunks


@router.post('/transcriptions')
def transcription(
    request: Request,
    file: UploadFile = File(...),
    language: Optional[str] = Form(None),
    user=Depends(get_verified_user),
):
    if user.role != 'admin' and not has_permission(user.id, 'chat.stt', request.app.state.config.USER_PERMISSIONS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    log.info(f'file.content_type: {file.content_type}')
    stt_supported_content_types = getattr(request.app.state.config, 'STT_SUPPORTED_CONTENT_TYPES', [])

    if not strict_match_mime_type(stt_supported_content_types, file.content_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.FILE_NOT_SUPPORTED,
        )

    try:
        safe_name = os.path.basename(file.filename) if file.filename else ''
        ext = safe_name.rsplit('.', 1)[-1] if '.' in safe_name else ''

        id = uuid.uuid4()

        filename = f'{id}.{ext}'
        contents = file.file.read()

        file_dir = f'{CACHE_DIR}/audio/transcriptions'
        os.makedirs(file_dir, exist_ok=True)
        file_path = f'{file_dir}/{filename}'

        # Defense-in-depth: ensure resolved path stays within intended directory
        if not os.path.realpath(file_path).startswith(os.path.realpath(file_dir)):
            raise ValueError('Invalid file path detected')

        with open(file_path, 'wb') as f:
            f.write(contents)

        try:
            metadata = None

            if language:
                metadata = {'language': language}

            result = transcribe(request, file_path, metadata, user)

            return {
                **result,
                'filename': os.path.basename(file_path),
            }

        except HTTPException:
            raise
        except Exception as e:
            log.exception(e)

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Transcription failed.',
            )

    except HTTPException:
        raise
    except Exception as e:
        log.exception(e)

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Transcription failed.',
        )


@router.get('/models')
async def get_models(request: Request, user=Depends(get_verified_user)):
    """In offline mode, no cloud TTS models are available."""
    return {'models': []}


@router.get('/voices')
async def get_voices(request: Request, user=Depends(get_verified_user)):
    """In offline mode, no cloud TTS voices are available."""
    return {'voices': []}
