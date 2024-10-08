# pylint: disable=line-too-long, no-member

from __future__ import print_function

import json

import requests

from django.conf import settings
from django.utils.text import slugify

SKIP_FIELD_NAMES = (
    'url',
)

DEFAULT_FIELD_PRIORITIES = (
    'text',
    'caption',
    'fullText',
    'full_text',
    'post',
    'comment',
    'description',
    'title',
    'name',
    'place',
    'location',
)

DETOXIFY_MODELS = (
    'original',
    'unbiased',
    'multilingual',
)

def annotate(content, field_name=None): # pylint: disable=too-many-branches, too-many-statements, too-many-locals
    if field_name in SKIP_FIELD_NAMES:
        return {}

    scores = {}

    if content is None:
        content = ''


    content = content.strip()

    if len(content) == 0: # pylint: disable=len-as-condition
        return {}

    try:
        data = {
            's': content
        }

        response = requests.post(settings.SIMPLE_DETOXIFY_URL, data=data, timeout=60)

        if response.ok:
            remote_scores = response.json()

            if 'to_score' in remote_scores:
                try:
                    if settings.SIMPLE_DETOXIFY_RETAIN_SCORED_TEXT is False:
                        del remote_scores['to_score']
                except AttributeError:
                    del remote_scores['to_score']

            for model in remote_scores:
                scores[slugify(model).replace('-', '_')] = remote_scores[model]
        else:
            print('REMOTE ERROR: %s:\n%s' % (response.status_code, response.text))

    except AttributeError:
        from detoxify import Detoxify # pylint: disable=import-error, import-outside-toplevel

        for model in DETOXIFY_MODELS:
            model_scores = Detoxify(model).predict(content)

            for key in model_scores.copy():
                model_scores[key] = float(model_scores[key])

            scores[slugify(model).replace('-', '_')] = model_scores

        print('GOT LOCAL: %s' % json.dumps(scores, indent=2))

    annotation_field = 'pdk_detoxify'

    if field_name is not None:
        annotation_field = 'pdk_detoxify_' + field_name

    return {
        annotation_field: scores,
        # 'cleartext': content,
    }


def fetch_annotation_fields():
    # labels = []

    # for model in DETOXIFY_MODELS:
    #    labels.append(slugify(model).replace('-', '_'))

    labels = [
        'unbiased_severe_toxicity',
        'unbiased_sexual_explicit',
        'unbiased_obscene',
        'unbiased_insult',
        'unbiased_threat',
        'unbiased_identity_attack',
        'unbiased_toxicity',
        'multilingual_severe_toxicity',
        'multilingual_sexual_explicit',
        'multilingual_obscene',
        'multilingual_insult',
        'multilingual_threat',
        'multilingual_identity_attack',
        'multilingual_toxicity',
        'original_severe_toxicity',
        'original_obscene',
        'original_insult',
        'original_threat',
        'original_identity_attack',
        'original_toxicity',
    ]

    return labels


def fetch_annotations(properties, initial_field=None): # pylint: disable=too-many-return-statements, too-many-branches
    if isinstance(properties, dict) is False:
        return None

    field_priorities = DEFAULT_FIELD_PRIORITIES

    try:
        field_priorities = settings.PDK_CONTENT_ANALYSIS_FIELD_PRIORITIES
    except AttributeError:
        pass

    if initial_field is None:
        for field in field_priorities:
            toxic_scores_key = 'pdk_detoxify_' + field

            if toxic_scores_key in properties:
                annotations = {}

                for model in properties[toxic_scores_key]:
                    for label in properties[toxic_scores_key][model]:
                        annotations[('%s_%s' % (model, label)).lower()] = properties.get(toxic_scores_key, {}).get(model, {}).get(label, '')

                return annotations

            annotations = fetch_annotations(properties, field)

            if annotations is not None:
                return annotations
    else:
        toxic_scores_key = 'pdk_detoxify_' + initial_field

        if toxic_scores_key in properties:
            annotations = {}

            for model in properties.get(toxic_scores_key, {}):
                for label in properties.get(toxic_scores_key, {}).get(model, {}):
                    annotations[('%s_%s' % (model, label)).lower()] = properties.get(toxic_scores_key, {}).get(model, {}).get(label, '')

            return annotations

        for key in properties:
            value = properties[key]

            if isinstance(value, dict):
                annotations = fetch_annotations(value, initial_field)

                if annotations is not None:
                    return annotations

            elif isinstance(value, list):
                for item in value:
                    annotations = fetch_annotations(item, initial_field)

                    if annotations is not None:
                        return annotations

    return None
