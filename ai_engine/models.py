from django.db import models

from tenders.models import Tender


class SolicitationDocument(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='solicitation_documents')
    file = models.FileField(upload_to='solicitation_documents/%Y/%m/')
    extracted_text = models.TextField(blank=True)
    analysis_summary = models.JSONField(default=dict, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return f'Solicitation document for {self.tender}'


class TenderAnalysisRun(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='analysis_runs')
    source_file = models.FileField(upload_to='analysis_uploads/%Y/%m/', blank=True)
    status = models.CharField(max_length=40, default='PLACEHOLDER_COMPLETE')
    raw_output = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Analysis for {self.tender}'


class TenderChatMessage(models.Model):
    tender = models.ForeignKey(Tender, on_delete=models.CASCADE, related_name='chat_messages')
    solicitation_document = models.ForeignKey(
        SolicitationDocument,
        on_delete=models.SET_NULL,
        related_name='chat_messages',
        blank=True,
        null=True,
    )
    question = models.TextField()
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Chat for {self.tender}: {self.question[:60]}'
